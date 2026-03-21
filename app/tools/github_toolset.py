"""GitHub MCP toolset: repository management via official GitHub MCP Server.

Uses the official github/github-mcp-server via MCPServerStdio (local process).
Provides agents with GitHub tools: repos, issues, PRs, files, branches, search.

Requires:
  - GITHUB_PERSONAL_ACCESS_TOKEN env var
  - npx available (Node.js installed in container)

Graceful degradation: if npx or the token is not available, returns None.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic_ai.toolsets import AbstractToolset

logger = logging.getLogger(__name__)


def create_github_toolset() -> AbstractToolset[Any] | None:
    """Create an MCP toolset connected to the GitHub MCP Server.

    Runs the official GitHub MCP Server as a local stdio process via npx.
    Returns None if GITHUB_PERSONAL_ACCESS_TOKEN is not set.

    Returns:
        MCPServerStdio toolset, or None if not configured.
    """
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
    if not token:
        logger.info("GITHUB_PERSONAL_ACCESS_TOKEN not set, GitHub tools disabled")
        return None

    try:
        from pydantic_ai.mcp import MCPServerStdio

        server = MCPServerStdio(
            "npx",
            ["-y", "@modelcontextprotocol/server-github"],
            env={
                **os.environ,
                "GITHUB_PERSONAL_ACCESS_TOKEN": token,
            },
        )
        logger.info("GitHub MCP toolset configured (stdio)")
        return server
    except Exception as e:
        logger.warning(f"GitHub MCP toolset failed: {e}")
        return None
