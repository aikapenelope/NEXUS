"""Backward-compatible re-export of deep agent configs.

Agent definitions have moved to app/agents/definitions/.
This module re-exports them for backward compatibility with
existing code that imports from here (e.g., copilot.py).
"""

from app.agents.definitions.deep_tools import CODER, RESEARCHER, REVIEWER

# All deep agent configs for easy iteration.
DEEP_AGENTS = {
    "nexus-coder": CODER,
    "nexus-reviewer": REVIEWER,
    "nexus-researcher": RESEARCHER,
}

__all__ = ["CODER", "DEEP_AGENTS", "RESEARCHER", "REVIEWER"]
