"""Code-defined agent configurations for the NEXUS platform.

Agents are organized into two categories:
  - CODING_AGENTS: For software engineering tasks (the core purpose)
  - GENERAL_AGENTS: For research, content, monitoring (secondary)

The AGENTS registry contains ALL agents for backward compatibility.
"""

from app.agents.definitions.content_writer import CONTENT_WRITER
from app.agents.definitions.data_analyst import DATA_ANALYST
from app.agents.definitions.deep_tools import CODER, RESEARCHER, REVIEWER
from app.agents.definitions.developer import DEVELOPER
from app.agents.definitions.general_assistant import GENERAL_ASSISTANT
from app.agents.definitions.research_analyst import RESEARCH_ANALYST
from app.agents.definitions.social_media import SOCIAL_MEDIA
from app.agents.definitions.web_monitor import WEB_MONITOR
from app.agents.factory import AgentConfig

# ── Coding agents (primary purpose) ─────────────────────────────────
CODING_AGENTS: dict[str, AgentConfig] = {}
for _config in [DEVELOPER, CODER, REVIEWER, RESEARCHER]:
    CODING_AGENTS[_config.name] = _config

# ── General agents (secondary) ──────────────────────────────────────
GENERAL_AGENTS: dict[str, AgentConfig] = {}
for _config in [
    RESEARCH_ANALYST,
    CONTENT_WRITER,
    WEB_MONITOR,
    DATA_ANALYST,
    SOCIAL_MEDIA,
    GENERAL_ASSISTANT,
]:
    GENERAL_AGENTS[_config.name] = _config

# ── All agents (backward compatibility) ─────────────────────────────
AGENTS: dict[str, AgentConfig] = {**CODING_AGENTS, **GENERAL_AGENTS}

__all__ = [
    "AGENTS",
    "CODER",
    "CODING_AGENTS",
    "CONTENT_WRITER",
    "DATA_ANALYST",
    "DEVELOPER",
    "GENERAL_AGENTS",
    "GENERAL_ASSISTANT",
    "RESEARCH_ANALYST",
    "RESEARCHER",
    "REVIEWER",
    "SOCIAL_MEDIA",
    "WEB_MONITOR",
]
