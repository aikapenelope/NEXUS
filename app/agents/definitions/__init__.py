"""Code-defined agent configurations for the NEXUS platform.

Each module exports one or more AgentConfig objects. These are the production
agents — defined in code, version-controlled, reviewed before deployment.

Usage:
    from app.agents.definitions import AGENTS
    config = AGENTS["research-analyst"]
    result = await run_deep_agent(config, "Analyze the AI agent market")
"""

from app.agents.definitions.content_writer import CONTENT_WRITER
from app.agents.definitions.deep_tools import CODER, RESEARCHER, REVIEWER
from app.agents.definitions.research_analyst import RESEARCH_ANALYST
from app.agents.definitions.web_monitor import WEB_MONITOR
from app.agents.factory import AgentConfig

# Registry of all code-defined agents, keyed by name.
AGENTS: dict[str, AgentConfig] = {}

# Auto-register all agents from this package
for _config in [CODER, REVIEWER, RESEARCHER, RESEARCH_ANALYST, CONTENT_WRITER, WEB_MONITOR]:
    AGENTS[_config.name] = _config

__all__ = [
    "AGENTS",
    "CODER",
    "CONTENT_WRITER",
    "RESEARCH_ANALYST",
    "RESEARCHER",
    "REVIEWER",
    "WEB_MONITOR",
]
