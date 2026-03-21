"""Code-defined agent configurations for the NEXUS platform.

Each module exports one or more AgentConfig objects. These are the production
agents -- defined in code, version-controlled, reviewed before deployment.

Usage:
    from app.agents.definitions import AGENTS
    config = AGENTS["research-analyst"]
    result = await run_deep_agent(config, "Analyze the AI agent market")
"""

from app.agents.definitions.content_writer import CONTENT_WRITER
from app.agents.definitions.data_analyst import DATA_ANALYST
from app.agents.definitions.deep_tools import CODER, RESEARCHER, REVIEWER
from app.agents.definitions.general_assistant import GENERAL_ASSISTANT
from app.agents.definitions.research_analyst import RESEARCH_ANALYST
from app.agents.definitions.social_media import SOCIAL_MEDIA
from app.agents.definitions.web_monitor import WEB_MONITOR
from app.agents.factory import AgentConfig

# Registry of all code-defined agents, keyed by name.
AGENTS: dict[str, AgentConfig] = {}

# Auto-register all agents from this package
for _config in [
    CODER,
    REVIEWER,
    RESEARCHER,
    RESEARCH_ANALYST,
    CONTENT_WRITER,
    WEB_MONITOR,
    DATA_ANALYST,
    SOCIAL_MEDIA,
    GENERAL_ASSISTANT,
]:
    AGENTS[_config.name] = _config

__all__ = [
    "AGENTS",
    "CODER",
    "CONTENT_WRITER",
    "DATA_ANALYST",
    "GENERAL_ASSISTANT",
    "RESEARCH_ANALYST",
    "RESEARCHER",
    "REVIEWER",
    "SOCIAL_MEDIA",
    "WEB_MONITOR",
]
