"""Agent factory: builds pydantic-deep agents from declarative AgentConfig objects."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits
from pydantic_deep import DeepAgentDeps, StateBackend, create_deep_agent

from app.config import settings
from app.models import get_model_for_role


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

    # Limits
    token_limit: int | None = Field(default=None, description="Max total tokens per run")
    cost_budget_usd: float | None = Field(default=None, description="Max USD cost per run")


def build_agent(config: AgentConfig) -> Agent[DeepAgentDeps, str]:
    """Instantiate a pydantic-deep agent from an AgentConfig.

    Applies model routing based on role, enforces token limits via
    UsageLimits, and sets cost_budget_usd for the cost tracking middleware.
    """
    model = get_model_for_role(config.role)

    # Resolve token limit: explicit config > role-based default
    token_limit = config.token_limit
    if token_limit is None:
        if config.role == "builder":
            token_limit = settings.builder_token_limit
        elif config.role == "analysis":
            token_limit = settings.cerebro_step_token_limit
        else:
            token_limit = settings.worker_token_limit

    # Resolve cost budget: explicit config > role-based default
    cost_budget = config.cost_budget_usd
    if cost_budget is None:
        if config.role == "builder":
            cost_budget = settings.builder_cost_budget
        elif config.role == "analysis":
            cost_budget = settings.cerebro_cost_budget
        else:
            cost_budget = settings.worker_cost_budget

    agent: Agent[DeepAgentDeps, str] = create_deep_agent(
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
    )
    return agent


async def run_agent(
    config: AgentConfig,
    prompt: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Build an agent from config, run it with the given prompt, return results.

    If user_id is provided, Mem0 semantic memory is searched for relevant
    context and injected into the prompt. After the run, the conversation
    is saved back to Mem0 for future recall.

    Returns a dict with the agent output and usage metadata.
    """
    agent = build_agent(config)
    deps = DeepAgentDeps(backend=StateBackend())

    # Resolve token limit for UsageLimits
    token_limit = config.token_limit
    if token_limit is None:
        if config.role in ("builder", "analysis"):
            token_limit = settings.builder_token_limit
        else:
            token_limit = settings.worker_token_limit

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

    # NOTE: Memory save removed here to avoid double writes.
    # The copilot's memory_add_tool handles saves when the LLM decides
    # to remember something, giving it control over what gets stored.

    return {
        "output": result.output,
        "usage": {
            "requests": result.usage().requests,
            "input_tokens": result.usage().input_tokens,
            "output_tokens": result.usage().output_tokens,
            "total_tokens": result.usage().total_tokens,
        },
    }
