"""Agent architect: analyzes requirements and produces Python code for agent definitions.

Instead of generating AgentConfig objects that get saved to the DB (the old builder
pattern), this agent acts as a consultant: it understands what you need, asks
clarifying questions, and outputs ready-to-use Python code for app/agents/definitions/.

The output is code you review and commit -- not a runtime-generated config that
nobody audits.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from app.config import settings
from app.models import HAIKU_MODEL

ARCHITECT_INSTRUCTIONS = """\
You are the NEXUS Agent Architect. Your job is to help users design AI agents
by understanding their requirements and producing Python code they can add to
their codebase.

PLATFORM CONTEXT:
NEXUS is a self-hosted AI agent platform built on pydantic-deep. Agents are
defined as AgentConfig objects in Python files under app/agents/definitions/.

AVAILABLE MODELS (via role routing):
- "worker" role -> Groq GPT-OSS 20B: fast, cheap ($0.075/1M input).
- "analysis" role -> Claude Haiku 4.5: smarter ($1/1M input).

AVAILABLE FEATURES (AgentConfig fields):
- include_todo, include_web, include_memory, include_filesystem,
  include_subagents, include_skills, include_execute, context_manager,
  skill_dir, token_limit, cost_budget_usd

YOUR PROCESS:
1. Ask clarifying questions about the agent's purpose, inputs, outputs.
2. Recommend which features to enable and why.
3. Produce a complete Python file with the AgentConfig definition.

Always output a complete Python file for app/agents/definitions/<name>.py.
NEVER produce an AgentConfig without explicit, detailed instructions.
"""

_architect_agent: Agent[None, str] | None = None


def _get_architect_agent() -> Agent[None, str]:
    """Return the architect agent, creating it on first call."""
    global _architect_agent  # noqa: PLW0603
    if _architect_agent is None:
        _architect_agent = Agent(
            model=HAIKU_MODEL,
            output_type=str,
            instructions=ARCHITECT_INSTRUCTIONS,
            retries=2,
        )
    return _architect_agent


async def design_agent(description: str) -> str:
    """Analyze requirements and produce Python code for an agent definition.

    Args:
        description: What the user wants the agent to do, with context.

    Returns:
        Python code string for the agent definition file.
    """
    agent = _get_architect_agent()
    result = await agent.run(
        description,
        usage_limits=UsageLimits(total_tokens_limit=settings.builder_token_limit),
    )
    return result.output


# Backward compatibility: keep the old function name as an alias
async def build_agent_from_description(description: str) -> str:
    """Deprecated alias for design_agent. Returns code instead of AgentConfig."""
    return await design_agent(description)
