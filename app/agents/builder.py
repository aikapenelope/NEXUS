"""Builder agent: translates natural language into AgentConfig via structured output.

This is the meta-agent that powers the "create an agent via natural language"
feature (twin.so style). It uses Claude Haiku to understand what the user wants
and produces a validated AgentConfig that can be passed to build_agent().
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from app.agents.factory import AgentConfig
from app.config import settings
from app.models import HAIKU_MODEL

BUILDER_INSTRUCTIONS = """\
You are the NEXUS Agent Builder. Your job is to translate a user's natural
language description of an AI agent into a structured AgentConfig.

Guidelines:
- name: short, lowercase, dash-separated identifier (e.g. "sales-researcher")
- description: one clear sentence about what the agent does
- instructions: a detailed system prompt / persona for the agent, written in
  second person ("You are..."). Include specific behaviors, tone, and constraints.
- role: choose based on the task complexity:
    - "worker" for simple tasks (research, extraction, summarization) — uses Groq (free)
    - "analysis" for complex reasoning, synthesis, judgment — uses Haiku (paid)
    - "builder" is reserved for this meta-agent, do not assign it
- Enable only the features the agent actually needs to minimize token usage:
    - include_todo: for multi-step tasks that benefit from planning
    - include_filesystem: only if the agent needs to read/write files
    - include_subagents: only if the agent needs to delegate to sub-agents
    - include_skills: only if the agent needs modular skill loading
    - include_memory: for agents that need to remember across sessions
    - include_web: for agents that need web search or URL fetching
    - context_manager: keep True unless the agent handles very short conversations
- token_limit and cost_budget_usd: leave as null to use role-based defaults,
  or set explicitly if the user specifies constraints

Always produce a valid AgentConfig. If the user's description is vague,
make reasonable assumptions and note them in the instructions field.
"""

# Lazy singleton — created on first use so env vars are available at runtime,
# not at import time (avoids crashes during Docker build / testing).
_builder_agent: Agent[None, AgentConfig] | None = None


def _get_builder_agent() -> Agent[None, AgentConfig]:
    """Return the builder agent, creating it on first call."""
    global _builder_agent  # noqa: PLW0603
    if _builder_agent is None:
        _builder_agent = Agent(
            model=HAIKU_MODEL,
            output_type=AgentConfig,
            instructions=BUILDER_INSTRUCTIONS,
            retries=2,
        )
    return _builder_agent


async def build_agent_from_description(description: str) -> AgentConfig:
    """Take a natural language description and return a validated AgentConfig.

    Args:
        description: What the user wants the agent to do, in plain language.

    Returns:
        A validated AgentConfig ready to pass to build_agent().
    """
    agent = _get_builder_agent()
    result = await agent.run(
        description,
        usage_limits=UsageLimits(total_tokens_limit=settings.builder_token_limit),
    )
    return result.output
