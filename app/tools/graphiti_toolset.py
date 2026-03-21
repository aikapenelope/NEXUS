"""Graphiti knowledge graph toolset for NEXUS agents.

Connects to the Graphiti MCP server (FalkorDB-backed temporal knowledge graph)
via Pydantic AI's MCPServerStreamableHTTP. Provides agents with persistent,
structured memory that tracks entities, relationships, and facts over time.

The MCP server exposes tools for:
  - add_episode: Store interactions/data in the knowledge graph
  - search_facts: Find relevant facts (edges) by semantic query
  - search_nodes: Find entities (nodes) by semantic query
  - get_episodes: Retrieve episodes by group
  - delete_episode: Remove an episode

Connection: http://graphiti:8000/mcp/ (internal Docker network)

Graceful degradation: if Graphiti is not running, returns None and
agents work without knowledge graph memory.
"""

from __future__ import annotations

import logging
import os

from pydantic_ai.mcp import MCPServerStreamableHTTP

logger = logging.getLogger(__name__)

# Default MCP endpoint (internal Docker network)
_DEFAULT_GRAPHITI_URL = "http://graphiti:8000/mcp/"


def create_graphiti_toolset() -> MCPServerStreamableHTTP | None:
    """Create an MCP toolset connected to the Graphiti knowledge graph server.

    Returns None if the GRAPHITI_MCP_URL env var is explicitly set to empty,
    allowing graceful degradation when Graphiti is not deployed.

    Returns:
        MCPServerStreamableHTTP toolset, or None if disabled.
    """
    url = os.environ.get("GRAPHITI_MCP_URL", _DEFAULT_GRAPHITI_URL)

    if not url:
        logger.info("Graphiti MCP disabled (GRAPHITI_MCP_URL is empty)")
        return None

    logger.info(f"Graphiti MCP toolset configured: {url}")
    return MCPServerStreamableHTTP(url=url)
