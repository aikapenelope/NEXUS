"""Agent factory: builds pydantic-deep agents from declarative AgentConfig objects.

Supports two execution backends:
  - StateBackend (in-memory): For simple agents without filesystem access.
  - DockerBackend (sandbox): For deep agents that need isolated code execution.
    Requires Docker socket mount and the nexus-sandbox image.

Deep agents (use_sandbox=True) get production-grade features matching the
pydantic-deep full_app reference implementation:
  - Hooks: safety_gate (blocks dangerous commands) + audit_logger (logs tool calls)
  - Middleware: AuditMiddleware (tool stats) + PermissionMiddleware (path blocking)
  - Processors: EvictionProcessor, SlidingWindowProcessor, PatchToolCallsProcessor
  - Checkpointing: save/rewind/fork conversations
  - Context files: DEEP.md injected into system prompt
  - Image support: multimodal read_file for images
  - Shell execution: execute tool with human-in-the-loop approval
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
# Hooks (Claude Code-style lifecycle hooks) — identical to Vstorm full_app
# ---------------------------------------------------------------------------


async def _audit_logger_handler(hook_input: HookInput) -> HookResult:
    """Background POST_TOOL_USE hook: logs all tool calls.

    Runs as fire-and-forget (non-blocking) so it doesn't slow down the agent.
    """
    args_preview = str(hook_input.tool_input)[:200]
    logger.info(f"HOOK AUDIT: {hook_input.tool_name}({args_preview})")
    return HookResult(allow=True)


async def _safety_gate_handler(hook_input: HookInput) -> HookResult:
    """PRE_TOOL_USE hook: blocks dangerous commands in execute tool.

    Returns allow=False to prevent the tool from executing when the command
    matches a dangerous pattern.  Only matches the 'execute' tool.
    """
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


_DEEP_AGENT_HOOKS = [
    # Background audit logger — fires after every tool completes
    Hook(
        event=HookEvent.POST_TOOL_USE,
        handler=_audit_logger_handler,
        background=True,
    ),
    # Safety gate — blocks dangerous execute commands (blocking, not background)
    Hook(
        event=HookEvent.PRE_TOOL_USE,
        handler=_safety_gate_handler,
        matcher="execute",
        timeout=5,
    ),
]


# ---------------------------------------------------------------------------
# AgentConfig model
# ---------------------------------------------------------------------------


class AgentConfig(BaseModel):
    """Declarative configuration for building a NEXUS agent.

    This is the output of the builder agent: a natural-language description
    gets translated into one of these, which then maps directly to
    create_deep_agent() parameters.
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
    include_memory: bool = Field(default=False, description="Enable persistent MEMORY.md")
    include_web: bool = Field(default=False, description="Enable web search/fetch tools")
    context_manager: bool = Field(default=True, description="Enable auto context compression")

    # Sandbox: when True and include_filesystem is True, use DockerBackend
    use_sandbox: bool = Field(
        default=False,
        description="Run in Docker sandbox (isolated code execution).",
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

    Returns DockerSandbox for sandboxed agents, StateBackend otherwise.
    DockerSandbox is imported lazily to avoid hard dependency on docker package
    when not using sandbox mode.
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
            # Fallback if sandbox extra not installed
            pass
    return StateBackend()


# ---------------------------------------------------------------------------
# Agent builder
# ---------------------------------------------------------------------------


def build_agent(config: AgentConfig) -> Agent[DeepAgentDeps, str]:
    """Instantiate a pydantic-deep agent from an AgentConfig.

    Simple agents (use_sandbox=False) get basic features only.
    Deep agents (use_sandbox=True) get full production features matching
    the pydantic-deep full_app reference: hooks, middleware, processors,
    checkpointing, context files, image support, and shell execution.
    """
    model = get_model_for_role(config.role)
    cost_budget = _resolve_cost_budget(config)

    # Disable web_search approval to prevent DeferredToolRequests from being
    # added to the agent's output_type.  When DeferredToolRequests is in the
    # union, AG-UI streaming and the copilot context cannot handle the output
    # correctly, causing runtime failures.  Setting web_search=False in
    # interrupt_on keeps the web tools available without the deferred wrapper.
    interrupt_on: dict[str, bool] | None = None
    if config.include_web:
        interrupt_on = {"web_search": False}

    # --- Deep agent (sandbox): add production features ---
    if config.use_sandbox and config.include_filesystem:
        from app.agents.deep.middleware import AuditMiddleware, PermissionMiddleware

        # Merge interrupt_on with execute approval
        sandbox_interrupt = dict(interrupt_on or {})
        sandbox_interrupt["execute"] = True

        # Sliding window processor for long conversations
        sliding_window = create_sliding_window_processor(
            trigger=("messages", 50),
            keep=("messages", 30),
        )

        # Resolve skills directory (only if it exists)
        skill_dirs: list[str] | None = None
        if _SKILLS_DIR.is_dir():
            skill_dirs = [str(_SKILLS_DIR)]

        # Resolve context files (only if DEEP.md exists)
        context_files: list[str] | None = None
        deep_md = _WORKSPACE_DIR / "DEEP.md"
        if deep_md.is_file():
            context_files = ["/workspace/DEEP.md"]

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
            include_execute=True,
            # --- Skills (SKILL.md files from Vstorm) ---
            skill_directories=skill_dirs,
            # --- Hooks (safety + audit, identical to Vstorm full_app) ---
            hooks=_DEEP_AGENT_HOOKS,
            # --- Middleware (audit stats + path blocking) ---
            middleware=[AuditMiddleware(), PermissionMiddleware()],
            # --- Processors ---
            eviction_token_limit=20000,
            patch_tool_calls=True,
            history_processors=[sliding_window],
            # --- Context files (DEEP.md auto-injection) ---
            context_files=context_files,
            # --- Image support (multimodal read_file) ---
            image_support=True,
            # --- Checkpointing (save/rewind/fork) ---
            include_checkpoints=True,
            checkpoint_frequency="every_turn",
            max_checkpoints=20,
            # --- Context management ---
            context_manager=config.context_manager,
            # --- Cost tracking ---
            cost_tracking=True,
            cost_budget_usd=cost_budget,
            # --- Human-in-the-loop ---
            interrupt_on=sandbox_interrupt,
        )
        return agent

    # --- Simple agent (no sandbox): basic features only ---
    agent = create_deep_agent(
        model=model,
        instructions=config.instructions,
        include_todo=config.include_todo,
        include_filesystem=config.include_filesystem,
        include_subagents=config.include_subagents,
        include_skills=config.include_skills,
        include_memory=config.include_memory,
        include_web=config.include_web,
        context_manager=config.context_manager,
        cost_tracking=True,
        cost_budget_usd=cost_budget,
        interrupt_on=interrupt_on,
    )
    return agent


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


async def run_agent(
    config: AgentConfig,
    prompt: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Build an agent from config, run it with the given prompt, return results.

    Delegates to run_deep_agent for full deep agent execution.
    Returns a dict with the agent output and usage metadata.
    """
    return await run_deep_agent(config, prompt, user_id=user_id)


async def run_deep_agent(
    config: AgentConfig,
    prompt: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Build and run a full pydantic-deep agent (with sub-agents, tools, etc.).

    Results are cached in Redis by hash(agent_name + prompt) with a 5-minute
    TTL.  Cache is best-effort: if Redis is down, the agent runs normally.

    Uses DockerBackend when config.use_sandbox is True, StateBackend otherwise.

    Returns a dict with the agent output and usage metadata.
    """
    from app.cache import get_cached_result, set_cached_result

    # Check cache first
    cached = await get_cached_result(config.name, prompt)
    if cached is not None:
        return cached

    agent = build_agent(config)
    backend = _create_backend(config)
    deps = DeepAgentDeps(backend=backend)

    token_limit = _resolve_token_limit(config)

    # Inject Mem0 semantic memory context if user_id is provided
    enriched_prompt = prompt
    if user_id:
        try:
            from app.memory import search_memory

            memories = await search_memory(query=prompt, user_id=user_id, agent_id=config.name)
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
            pass  # Memory is best-effort, don't block agent execution

    result = await agent.run(
        enriched_prompt,
        deps=deps,
        usage_limits=UsageLimits(total_tokens_limit=token_limit),
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

    # Cache the result (best-effort, non-blocking)
    await set_cached_result(config.name, prompt, output)

    return output
