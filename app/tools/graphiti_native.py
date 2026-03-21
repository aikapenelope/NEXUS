"""Graphiti native toolset: temporal knowledge graph via graphiti-core.

Uses graphiti-core Python library directly (no MCP). Connects to FalkorDB
running in the nexus-graphiti container. Provides agents with persistent,
structured memory that tracks entities, relationships, and facts over time.

Tools:
  - remember_knowledge: Store a fact/interaction in the knowledge graph
  - search_knowledge_graph: Search for facts by semantic query
  - search_entities: Search for entities (people, projects, concepts)

Connection is lazy -- only connects when a tool is actually called,
avoiding the init-time crash that MCP toolsets have.

Graceful degradation: if graphiti-core is not installed or FalkorDB
is not running, tools return error messages instead of crashing.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset
from pydantic_deep import DeepAgentDeps

logger = logging.getLogger(__name__)

# FalkorDB connection (same container network as docker-compose)
_DEFAULT_FALKORDB_URI = "bolt://graphiti:6379"

# Lazy singleton -- created on first tool call
_graphiti_client: Any = None
_graphiti_init_failed = False


async def _get_graphiti() -> Any:
    """Get or create the Graphiti client. Lazy initialization."""
    global _graphiti_client, _graphiti_init_failed  # noqa: PLW0603

    if _graphiti_init_failed:
        return None

    if _graphiti_client is not None:
        return _graphiti_client

    try:
        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.llm_client.openai_client import OpenAIClient

        api_key = os.environ.get("OPENAI_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        falkordb_uri = os.environ.get("FALKORDB_URI", _DEFAULT_FALKORDB_URI)

        if not api_key:
            logger.warning("OPENAI_API_KEY not set, Graphiti disabled")
            _graphiti_init_failed = True
            return None

        llm_client = OpenAIClient(
            config=LLMConfig(
                api_key=api_key,
                model="openai/gpt-4o-mini",
                base_url=base_url,
            )
        )

        embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=api_key,
                base_url=base_url,
            )
        )

        driver = FalkorDriver(
            host=falkordb_uri.replace("bolt://", "").split(":")[0],
            port=int(falkordb_uri.split(":")[-1]) if ":" in falkordb_uri else 6379,
        )

        _graphiti_client = Graphiti(
            uri=falkordb_uri,
            llm_client=llm_client,
            embedder=embedder,
            graph_driver=driver,
        )

        await _graphiti_client.build_indices_and_constraints()
        logger.info(f"Graphiti connected to {falkordb_uri}")
        return _graphiti_client

    except Exception as e:
        logger.warning(f"Graphiti init failed: {e}")
        _graphiti_init_failed = True
        return None


def create_graphiti_native_toolset(
    toolset_id: str = "graphiti",
) -> FunctionToolset[DeepAgentDeps]:
    """Create a FunctionToolset with native Graphiti knowledge graph tools.

    Tools connect lazily on first call -- no init-time connection.
    If Graphiti/FalkorDB is down, tools return error messages gracefully.
    """
    toolset: FunctionToolset[DeepAgentDeps] = FunctionToolset(id=toolset_id)

    @toolset.tool
    async def remember_knowledge(
        ctx: RunContext[DeepAgentDeps],
        text: str,
        source: str = "agent",
    ) -> str:
        """Store a fact or interaction in the temporal knowledge graph.

        Use this to remember important information that should persist
        across sessions: project architecture, user preferences, decisions,
        bug patterns, technology choices, etc.

        The knowledge graph automatically extracts entities and relationships
        from the text and tracks when facts change over time.

        Args:
            text: The information to store (natural language).
            source: Source label (e.g. "agent", "user", "code-review").
        """
        client = await _get_graphiti()
        if client is None:
            return "Knowledge graph unavailable. Information noted but not persisted."

        try:
            from datetime import datetime, timezone

            await client.add_episode(
                name=f"nexus-{source}",
                episode_body=text,
                source_description=f"NEXUS agent ({source})",
                reference_time=datetime.now(timezone.utc),
                group_id="nexus",
            )
            return f"Stored in knowledge graph: {text[:100]}..."
        except Exception as e:
            return f"Failed to store in knowledge graph: {e}"

    @toolset.tool
    async def search_knowledge_graph(
        ctx: RunContext[DeepAgentDeps],
        query: str,
        num_results: int = 5,
    ) -> str:
        """Search the temporal knowledge graph for relevant facts.

        Searches across entities, relationships, and facts using hybrid
        retrieval (semantic + keyword + graph traversal).

        Args:
            query: Natural language search query.
            num_results: Maximum number of results to return.
        """
        client = await _get_graphiti()
        if client is None:
            return "Knowledge graph unavailable."

        try:
            results = await client.search(query, num_results=num_results, group_ids=["nexus"])
            if not results:
                return "No results found in knowledge graph."

            lines = []
            for i, r in enumerate(results, 1):
                fact = getattr(r, "fact", None) or getattr(r, "content", str(r))
                score = getattr(r, "score", None)
                score_str = f" (score: {score:.2f})" if score else ""
                lines.append(f"{i}. {fact}{score_str}")

            return "Knowledge graph results:\n" + "\n".join(lines)
        except Exception as e:
            return f"Knowledge graph search failed: {e}"

    return toolset
