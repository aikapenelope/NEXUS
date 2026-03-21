"""Agent factory: builds pydantic-deep agents from declarative AgentConfig objects.

All agents get production-grade features regardless of backend:
  - Hooks: safety_gate (blocks dangerous commands) + audit_logger (logs tool calls)
  - Middleware: AuditMiddleware (tool stats) + PermissionMiddleware (path blocking)
  - Processors: EvictionProcessor, SlidingWindowProcessor, PatchToolCallsProcessor
  - Checkpointing: save/rewind/fork conversations via FileCheckpointStore
  - Context management: auto-summarization for long conversations
  - Cost tracking: USD budget enforcement with DB callback
  - Skills: loaded from per-agent skill directories
  - Memory: MEMORY.md persistent across sessions + Mem0 semantic injection

Backend selection:
  - use_sandbox=True + include_filesystem=True → DockerSandbox (isolated execution)
  - Otherwise → StateBackend (in-memory, no filesystem)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits
from pydantic_deep import (
    DeepAgentDeps,
    Hook,
    HookEvent,
    HookInput,
    HookResult,
    StateBackend,
    create_deep_agent,
    create_sliding_window_processor,
)

from app.config import settings
from app.models import get_model_for_role

logger = logging.getLogger(__name__)

# Path to skills and workspace context files (relative to this module).
_DEEP_DIR = Path(__file__).parent / "deep"
_SKILLS_DIR = _DEEP_DIR / "skills"
_WORKSPACE_DIR = _DEEP_DIR / "workspace"

# ---------------------------------------------------------------------------
# Hooks (Claude Code-style lifecycle hooks)
# ---------------------------------------------------------------------------


async def _audit_logger_handler(hook_input: HookInput) -> HookResult:
    """Background POST_TOOL_USE hook: logs all tool calls."""
    args_preview = str(hook_input.tool_input)[:200]
    logger.info(f"HOOK AUDIT: {hook_input.tool_name}({args_preview})")
    return HookResult(allow=True)


async def _safety_gate_handler(hook_input: HookInput) -> HookResult:
    """PRE_TOOL_USE hook: blocks dangerous commands in execute tool."""
    command = hook_input.tool_input.get("command", "")

    dangerous_patterns = [
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+\*",
        r"mkfs\.",
        r"dd\s+if=.*of=/dev/",
        r"chmod\s+-R\s+777\s+/",
        r":\(\)\{",  # fork bomb
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, command):
            return HookResult(
                allow=False,
                reason=(
                    f"BLOCKED: Command matches dangerous pattern. "
                    f"The command '{command}' was blocked for safety."
                ),
            )

    return HookResult(allow=True)


_HOOKS = [
    Hook(
        event=HookEvent.POST_TOOL_USE,
        handler=_audit_logger_handler,
        background=True,
    ),
    Hook(
        event=HookEvent.PRE_TOOL_USE,
        handler=_safety_gate_handler,
        matcher="execute",
        timeout=5,
    ),
]


# ---------------------------------------------------------------------------
# Cost tracking callback
# ---------------------------------------------------------------------------


async def _on_cost_update(cost_info: Any) -> None:
    """Persist cost data to the database for visibility.

    Called by CostTrackingMiddleware after each agent run.
    Best-effort: failures are logged but don't block execution.
    """
    try:
        from app.traces import save_cost_event

        await save_cost_event(
            run_cost_usd=getattr(cost_info, "run_cost_usd", 0.0),
            cumulative_cost_usd=getattr(cost_info, "cumulative_cost_usd", 0.0),
            input_tokens=getattr(cost_info, "input_tokens", 0),
            output_tokens=getattr(cost_info, "output_tokens", 0),
        )
    except Exception:
        logger.debug("Cost tracking callback failed", exc_info=True)


# ---------------------------------------------------------------------------
# AgentConfig model
# ---------------------------------------------------------------------------


class AgentConfig(BaseModel):
    """Declarative configuration for building a NEXUS agent.

    Every agent — whether simple or sandboxed — gets the full production
    feature set: hooks, middleware, processors, checkpointing, cost tracking.
    """

    name: str = Field(description="Short identifier for the agent")
    description: str = Field(description="What this agent does, in one sentence")
    instructions: str = Field(description="System prompt / persona for the agent")
    role: str = Field(
        default="worker",
        description="Model routing role: 'builder', 'analysis', or 'worker'",
    )

    # Feature toggles (map 1:1 to create_deep_agent kwargs)
    include_todo: bool = Field(default=True, description="Enable task planning")
    include_filesystem: bool = Field(default=False, description="Enable file read/write")
    include_subagents: bool = Field(default=False, description="Enable sub-agent delegation")
    include_skills: bool = Field(default=False, description="Enable skill loading")
    include_memory: bool = Field(default=True, description="Enable persistent MEMORY.md")
    include_web: bool = Field(default=False, description="Enable web search/fetch tools")
    context_manager: bool = Field(default=True, description="Enable auto context compression")

    # Sandbox: when True and include_filesystem is True, use DockerBackend
    use_sandbox: bool = Field(
        default=False,
        description="Run in Docker sandbox (isolated code execution).",
    )

    # Per-agent skill directory (relative to app/agents/knowledge/)
    skill_dir: str | None = Field(
        default=None,
        description="Subdirectory under app/agents/knowledge/ for this agent's skills",
    )

    # Limits
    token_limit: int | None = Field(default=None, description="Max total tokens per run")
    cost_budget_usd: float | None = Field(default=None, description="Max USD cost per run")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_token_limit(config: AgentConfig) -> int:
    """Resolve token limit: explicit config > role-based default."""
    if config.token_limit is not None:
        return config.token_limit
    if config.role == "builder":
        return settings.builder_token_limit
    if config.role == "analysis":
        return settings.cerebro_step_token_limit
    return settings.worker_token_limit


def _resolve_cost_budget(config: AgentConfig) -> float:
    """Resolve cost budget: explicit config > role-based default."""
    if config.cost_budget_usd is not None:
        return config.cost_budget_usd
    if config.role == "builder":
        return settings.builder_cost_budget
    if config.role == "analysis":
        return settings.cerebro_cost_budget
    return settings.worker_cost_budget


def _create_backend(config: AgentConfig) -> StateBackend | Any:
    """Create the appropriate backend for the agent.

    DockerSandbox for sandboxed agents with filesystem, StateBackend otherwise.
    """
    if config.use_sandbox and config.include_filesystem:
        try:
            from pydantic_deep import DockerSandbox

            return DockerSandbox(
                image=settings.sandbox_image,
                work_dir="/workspace",
                auto_remove=True,
                idle_timeout=settings.sandbox_timeout,
            )
        except ImportError:
            pass
    return StateBackend()


def _resolve_skill_dirs(config: AgentConfig) -> list[str] | None:
    """Resolve skill directories for the agent.

    Priority:
      1. Per-agent knowledge dir (app/agents/knowledge/{skill_dir}/)
      2. Shared skills dir (app/agents/deep/skills/) as fallback
    """
    dirs: list[str] = []

    # Per-agent knowledge directory
    if config.skill_dir:
        knowledge_dir = Path(__file__).parent / "knowledge" / config.skill_dir
        if knowledge_dir.is_dir():
            dirs.append(str(knowledge_dir))

    # Shared skills (fallback)
    if _SKILLS_DIR.is_dir():
        dirs.append(str(_SKILLS_DIR))

    return dirs if dirs else None


def _resolve_context_files(config: AgentConfig) -> list[str] | None:
    """Resolve context files (DEEP.md) for system prompt injection."""
    deep_md = _WORKSPACE_DIR / "DEEP.md"
    if deep_md.is_file():
        return [str(deep_md)]
    return None


# ---------------------------------------------------------------------------
# Agent builder — single unified path for all agents
# ---------------------------------------------------------------------------


def build_agent(config: AgentConfig) -> Agent[DeepAgentDeps, str]:
    """Instantiate a pydantic-deep agent from an AgentConfig.

    Every agent gets the full production feature set:
    hooks, middleware, processors, checkpointing, cost tracking.
    The only difference between sandbox and non-sandbox is the backend.
    """
    from app.agents.deep.middleware import AuditMiddleware, PermissionMiddleware

    model = get_model_for_role(config.role)
    cost_budget = _resolve_cost_budget(config)

    # Sliding window processor for long conversations
    sliding_window = create_sliding_window_processor(
        trigger=("messages", 50),
        keep=("messages", 30),
    )

    # Interrupt-on configuration
    interrupt_on: dict[str, bool] = {}
    if config.include_web:
        interrupt_on["web_search"] = False
    if config.use_sandbox and config.include_filesystem:
        interrupt_on["execute"] = True

    # Build the agent with all production features
    agent: Agent[DeepAgentDeps, str] = create_deep_agent(
        model=model,
        instructions=config.instructions,
        backend=None,  # Backend comes from deps at runtime
        # --- Toolsets ---
        include_todo=config.include_todo,
        include_filesystem=config.include_filesystem,
        include_subagents=config.include_subagents,
        include_skills=config.include_skills,
        include_memory=config.include_memory,
        include_web=config.include_web,
        include_execute=config.use_sandbox and config.include_filesystem,
        # --- Skills ---
        skill_directories=_resolve_skill_dirs(config),
        # --- Hooks (safety + audit) ---
        hooks=_HOOKS,
        # --- Middleware (audit stats + path blocking) ---
        middleware=[AuditMiddleware(), PermissionMiddleware()],
        # --- Processors ---
        eviction_token_limit=20000,
        patch_tool_calls=True,
        history_processors=[sliding_window],
        # --- Context files (DEEP.md injection) ---
        context_files=_resolve_context_files(config),
        # --- Image support ---
        image_support=True,
        # --- Checkpointing ---
        include_checkpoints=True,
        checkpoint_frequency="every_turn",
        max_checkpoints=20,
        # --- Context management ---
        context_manager=config.context_manager,
        # --- Cost tracking ---
        cost_tracking=True,
        cost_budget_usd=cost_budget,
        on_cost_update=_on_cost_update,
        # --- Human-in-the-loop ---
        interrupt_on=interrupt_on if interrupt_on else None,
    )
    return agent


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


async def run_deep_agent(
    config: AgentConfig,
    prompt: str,
    user_id: str | None = None,
    message_history: list[Any] | None = None,
) -> dict[str, Any]:
    """Build and run a pydantic-deep agent with full production features.

    Memory integration:
      1. Chat history: passed via message_history parameter
      2. Mem0 semantic: relevant facts injected into prompt if user_id provided
      3. MEMORY.md: handled by pydantic-deep internally (include_memory=True)

    Post-run: saves facts to Mem0 for cross-session retrieval.

    Returns a dict with the agent output and usage metadata.
    """
    from app.cache import get_cached_result, set_cached_result

    # Check cache first (skip if message_history provided — conversational)
    if not message_history:
        cached = await get_cached_result(config.name, prompt)
        if cached is not None:
            return cached

    agent = build_agent(config)
    backend = _create_backend(config)

    deps = DeepAgentDeps(backend=backend)

    token_limit = _resolve_token_limit(config)

    # --- Memory Layer 2: Inject Mem0 semantic context ---
    enriched_prompt = prompt
    if user_id:
        try:
            from app.memory import search_memory

            memories = await search_memory(
                query=prompt, user_id=user_id, agent_id=config.name
            )
            if memories:
                memory_lines = [
                    m.get("memory", m.get("text", ""))
                    for m in memories
                    if m.get("memory") or m.get("text")
                ]
                if memory_lines:
                    context = "\n".join(f"- {line}" for line in memory_lines)
                    enriched_prompt = (
                        f"Relevant memories about this user:\n{context}\n\n---\n\n{prompt}"
                    )
        except Exception:
            pass  # Memory is best-effort

    # --- Run the agent ---
    run_kwargs: dict[str, Any] = {
        "deps": deps,
        "usage_limits": UsageLimits(total_tokens_limit=token_limit),
    }
    if message_history:
        run_kwargs["message_history"] = message_history

    result = await agent.run(enriched_prompt, **run_kwargs)

    output = {
        "output": result.output,
        "usage": {
            "requests": result.usage().requests,
            "input_tokens": result.usage().input_tokens,
            "output_tokens": result.usage().output_tokens,
            "total_tokens": result.usage().total_tokens,
        },
    }

    # --- Post-run: save facts to Mem0 for cross-session memory ---
    if user_id:
        try:
            from app.memory import add_memory

            await add_memory(
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": result.output[:2000]},
                ],
                user_id=user_id,
                agent_id=config.name,
            )
        except Exception:
            pass  # Memory persistence is best-effort

    # Cache the result (skip if conversational)
    if not message_history:
        await set_cached_result(config.name, prompt, output)

    return output


# Keep backward compatibility
async def run_agent(
    config: AgentConfig,
    prompt: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible alias for run_deep_agent."""
    return await run_deep_agent(config, prompt, user_id=user_id)
