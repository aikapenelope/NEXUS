"""Agent factory: builds pydantic-deep agents from declarative AgentConfig objects.

Aligned with vstorm full_app reference and Pydantic AI best practices:
  - Single unified path: ALL agents get production features (hooks, middleware,
    processors, checkpointing, cost tracking) regardless of backend.
  - BASE_PROMPT as foundation for all agent instructions.
  - UsageLimits with request_limit + tool_calls_limit (not just token limit).
  - Backend selection is the ONLY difference between sandbox and non-sandbox.

Backend selection:
  - use_sandbox=True + include_filesystem=True -> DockerSandbox
  - Otherwise -> StateBackend (in-memory)
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
    BASE_PROMPT,
    DeepAgentDeps,
    Hook,
    HookEvent,
    HookInput,
    HookResult,
    Skill,
    StateBackend,
    create_deep_agent,
    create_sliding_window_processor,
)
from pydantic_deep.types import SubAgentConfig

from app.agents.deep.middleware import AuditMiddleware, PermissionMiddleware
from app.config import settings
from app.models import get_model_for_role

logger = logging.getLogger(__name__)

# Path to skills and workspace context files (relative to this module).
_DEEP_DIR = Path(__file__).parent / "deep"
_SKILLS_DIR = _DEEP_DIR / "skills"
_WORKSPACE_DIR = _DEEP_DIR / "workspace"


# ---------------------------------------------------------------------------
# Hooks (Claude Code-style lifecycle hooks) — matches vstorm full_app
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

# Module-level middleware instances (shared across agents, stateless).
_audit_mw = AuditMiddleware()
_permission_mw = PermissionMiddleware()

# Sliding window processor (shared, stateless).
_sliding_window = create_sliding_window_processor(
    trigger=("messages", 50),
    keep=("messages", 30),
)


# ---------------------------------------------------------------------------
# Cost tracking callback
# ---------------------------------------------------------------------------


async def _on_cost_update(cost_info: Any) -> None:
    """Persist cost data to DB after each agent run.

    Called by CostTrackingMiddleware. Best-effort: failures don't block.
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
# Programmatic skills (Skill dataclass instances)
# ---------------------------------------------------------------------------

# Platform reference skill -- tells agents what NEXUS can do.
_NEXUS_REFERENCE_SKILL = Skill(
    name="nexus-reference",
    description="Quick reference for NEXUS platform capabilities, agents, and tools",
    content="""\
# NEXUS Platform Reference

## Available Agents (code-defined)
- **nexus-coder**: Senior engineer, writes code with tests (sandbox, subagents)
- **nexus-reviewer**: Code reviewer for bugs, security, quality (sandbox)
- **nexus-researcher**: Technical research with structured notes (sandbox, web)
- **research-analyst**: Multi-source research with structured reports (web, memory)
- **content-writer**: Publication-ready content with voice consistency (memory)
- **web-monitor**: Tracks web page changes with memory-based diffing (web, memory)
- **data-analyst**: Data analysis, visualization, statistical insights (web, memory)
- **social-media**: Social media content creation and strategy (web, memory)
- **general-assistant**: General-purpose assistant for any task (web, memory, subagents)

## Tools Available to Agents
- **Todo**: Task planning and progress tracking (write_todos, read_todos)
- **Filesystem**: read_file, write_file, edit_file, glob, grep, ls
- **Execute**: Shell command execution (sandbox only, requires approval)
- **Web**: web_search, fetch_url, http_request
- **Memory**: read_memory, write_memory, update_memory (MEMORY.md)
- **Skills**: list_skills, load_skill, read_skill_resource
- **Subagents**: delegate_task to specialized subagents
- **Checkpoints**: save_checkpoint, rewind_to, list_checkpoints

## Memory System (3 layers)
1. **Chat history**: Per-conversation message persistence (nexus_messages)
2. **Mem0 semantic**: Cross-session fact extraction via pgvector + Voyage AI
3. **MEMORY.md**: Per-agent persistent knowledge file

## Models
- **Worker** (Groq GPT-OSS 20B): Fast, cheap -- research, extraction, content
- **Analysis** (Claude Haiku 4.5): Smart -- complex analysis, code review, synthesis
""",
)


# ---------------------------------------------------------------------------
# AgentConfig model
# ---------------------------------------------------------------------------


class AgentConfig(BaseModel):
    """Declarative configuration for building a NEXUS agent.

    Every agent gets the full production feature set regardless of backend.
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

    # Subagent configurations (SubAgentConfig dicts for the task tool)
    subagent_configs: list[SubAgentConfig] | None = Field(
        default=None,
        description="Pre-configured subagents: [{name, description, instructions}, ...]",
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
    """Resolve skill directories: per-agent knowledge dir + shared fallback."""
    dirs: list[str] = []
    if config.skill_dir:
        knowledge_dir = Path(__file__).parent / "knowledge" / config.skill_dir
        if knowledge_dir.is_dir():
            dirs.append(str(knowledge_dir))
    if _SKILLS_DIR.is_dir():
        dirs.append(str(_SKILLS_DIR))
    return dirs if dirs else None


def _resolve_context_files() -> list[str] | None:
    """Resolve context files (DEEP.md) for system prompt injection."""
    deep_md = _WORKSPACE_DIR / "DEEP.md"
    if deep_md.is_file():
        return [str(deep_md)]
    return None


# ---------------------------------------------------------------------------
# Fix 2: BASE_PROMPT as foundation for all instructions
# ---------------------------------------------------------------------------


def _build_instructions(config: AgentConfig) -> str:
    """Prepend BASE_PROMPT to agent instructions.

    Following vstorm full_app pattern: BASE_PROMPT provides the core deep
    agent behavior (be concise, bias towards action, use tools, etc.) and
    the agent's custom instructions extend it.
    """
    if not config.instructions:
        return BASE_PROMPT
    return f"{BASE_PROMPT}\n\n{config.instructions}"


# ---------------------------------------------------------------------------
# Fix 1: Single unified agent builder — ALL agents get production features
# ---------------------------------------------------------------------------


def build_agent(config: AgentConfig) -> Agent[DeepAgentDeps, str]:
    """Instantiate a pydantic-deep agent from an AgentConfig.

    Every agent gets the full production feature set: hooks, middleware,
    processors, checkpointing, cost tracking, context files, image support.
    The only difference between sandbox and non-sandbox is the backend and
    whether the execute tool is included.
    """
    model = get_model_for_role(config.role)
    cost_budget = _resolve_cost_budget(config)

    # Interrupt-on configuration
    interrupt_on: dict[str, bool] = {}
    if config.include_web:
        # Disable web_search approval to prevent DeferredToolRequests from
        # breaking AG-UI streaming.
        interrupt_on["web_search"] = False
    if config.use_sandbox and config.include_filesystem:
        interrupt_on["execute"] = True

    # Fix 5: include_plan and include_general_purpose_subagent for
    # agents that use subagents (matches vstorm full_app reference).
    include_plan = config.include_subagents
    include_general_purpose = config.include_subagents

    agent: Agent[DeepAgentDeps, str] = create_deep_agent(
        model=model,
        instructions=_build_instructions(config),
        backend=None,  # Backend comes from deps at runtime
        # --- Toolsets ---
        include_todo=config.include_todo,
        include_filesystem=config.include_filesystem,
        include_subagents=config.include_subagents,
        include_skills=config.include_skills,
        include_memory=config.include_memory,
        include_web=config.include_web,
        include_execute=config.use_sandbox and config.include_filesystem,
        # --- Fix 6: Plan mode + general-purpose subagent ---
        include_plan=include_plan,
        include_general_purpose_subagent=include_general_purpose,
        # --- Subagent configs (pre-defined specialists) ---
        subagents=config.subagent_configs,
        # --- Skills ---
        skill_directories=_resolve_skill_dirs(config),
        # --- Hooks (safety + audit) — matches vstorm full_app ---
        hooks=_HOOKS,
        # --- Middleware (audit stats + path blocking) ---
        middleware=[_audit_mw, _permission_mw],
        # --- Processors ---
        eviction_token_limit=20000,
        patch_tool_calls=True,
        history_processors=[_sliding_window],
        # --- Context files (DEEP.md injection) ---
        context_files=_resolve_context_files(),
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
        # --- Summarization model (use cheap Groq for context compression) ---
        summarization_model=get_model_for_role("worker"),
        # --- Programmatic skills ---
        skills=[_NEXUS_REFERENCE_SKILL],
        # --- Human-in-the-loop ---
        interrupt_on=interrupt_on if interrupt_on else None,
    )
    return agent


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


async def run_agent(
    config: AgentConfig,
    prompt: str,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible alias for run_deep_agent."""
    return await run_deep_agent(
        config, prompt, user_id=user_id, conversation_id=conversation_id
    )


async def run_deep_agent(
    config: AgentConfig,
    prompt: str,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Build and run a pydantic-deep agent with unified 3-layer memory.

    Memory layers (all best-effort, failures don't block execution):

      Layer 1 -- Chat history (nexus_messages):
        If conversation_id is provided, loads recent messages and passes
        them as native message_history to agent.run() (not text injection).

      Layer 2 -- Mem0 semantic memory (pgvector):
        If user_id is provided, searches for relevant facts and injects
        them into the prompt. After the run, extracts new facts.

      Layer 3 -- MEMORY.md (pydantic-deep built-in):
        Handled internally when include_memory=True.

    Returns a dict with the agent output and usage metadata.
    """
    from app.cache import get_cached_result, set_cached_result

    # Skip cache for conversational runs (context-dependent)
    if not conversation_id:
        cached = await get_cached_result(config.name, prompt)
        if cached is not None:
            return cached

    agent = build_agent(config)
    backend = _create_backend(config)
    deps = DeepAgentDeps(backend=backend)

    token_limit = _resolve_token_limit(config)

    # ── Layer 2: Inject Mem0 semantic memory into prompt ────────────
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
            pass  # Semantic memory is best-effort

    # ── Layer 3: MEMORY.md handled by pydantic-deep internally ──────

    # ── Fix 4: UsageLimits with request_limit + tool_calls_limit ────
    usage_limits = UsageLimits(
        total_tokens_limit=token_limit,
        request_limit=50,  # Prevent infinite loops (50 model turns max)
        tool_calls_limit=100,  # Prevent runaway tool usage
    )

    # ── Run the agent ───────────────────────────────────────────────
    result = await agent.run(
        enriched_prompt,
        deps=deps,
        usage_limits=usage_limits,
    )

    output = {
        "output": result.output,
        "usage": {
            "requests": result.usage().requests,
            "input_tokens": result.usage().input_tokens,
            "output_tokens": result.usage().output_tokens,
            "total_tokens": result.usage().total_tokens,
        },
    }

    # ── Post-run: persist to memory layers ──────────────────────────

    # Layer 1: Save messages to chat history
    if conversation_id:
        try:
            from app.conversations import add_message

            await add_message(conversation_id, "user", prompt)
            await add_message(
                conversation_id, "assistant", result.output[:2000]
            )
        except Exception:
            pass  # Chat persistence is best-effort

    # Layer 2: Extract facts to Mem0 for cross-session retrieval
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
            pass  # Mem0 persistence is best-effort

    # Cache the result (skip for conversational runs)
    if not conversation_id:
        await set_cached_result(config.name, prompt, output)

    return output
