"""Mem0 semantic memory service for NEXUS.

Level 3 memory: cross-agent, cross-session semantic memory backed by
PostgreSQL + pgvector for vector storage and HuggingFace local embeddings
(BAAI/bge-small-en-v1.5, 384 dims, CPU-only via fastembed).

Uses Anthropic (Claude Haiku) as the LLM for memory extraction/consolidation.
No OpenAI dependency.
"""

from __future__ import annotations

from typing import Any

from mem0 import Memory

from app.config import settings

# Lazy singleton — created on first use so env vars and DB are ready.
_memory: Memory | None = None


def _get_mem0_config() -> dict[str, Any]:
    """Build the Mem0 configuration dictionary.

    - Vector store: pgvector on the same Postgres instance
    - Embedder: HuggingFace local (fastembed, CPU-only, 384 dims)
    - LLM: Anthropic Claude Haiku for fact extraction/consolidation
    """
    # Parse DB URL components from settings
    # Format: postgresql://user:pass@host:port/dbname
    db_url = settings.database_url
    # Strip scheme
    rest = db_url.split("://", 1)[1]
    userpass, hostportdb = rest.split("@", 1)
    user, password = userpass.split(":", 1)
    hostport, dbname = hostportdb.split("/", 1)
    if ":" in hostport:
        host, port_str = hostport.split(":", 1)
        port = int(port_str)
    else:
        host = hostport
        port = 5432

    return {
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "user": user,
                "password": password,
                "host": host,
                "port": port,
                "dbname": dbname,
                "collection_name": "nexus_memories",
                "embedding_model_dims": 384,
            },
        },
        "embedder": {
            "provider": "huggingface",
            "config": {
                "model": "BAAI/bge-small-en-v1.5",
                "embedding_dims": 384,
            },
        },
        "llm": {
            "provider": "anthropic",
            "config": {
                "model": "claude-haiku-4-5-20251001",
                "temperature": 0.1,
                "max_tokens": 1500,
            },
        },
    }


def get_memory() -> Memory:
    """Return the Mem0 Memory singleton, creating it on first call."""
    global _memory  # noqa: PLW0603
    if _memory is None:
        config = _get_mem0_config()
        _memory = Memory.from_config(config)
    return _memory


async def add_memory(
    messages: list[dict[str, str]],
    user_id: str,
    agent_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add a conversation to semantic memory.

    Mem0 extracts facts from the messages and stores them as
    vector embeddings in pgvector for later retrieval.

    Args:
        messages: List of {"role": "user"|"assistant", "content": "..."}.
        user_id: User identifier for memory scoping.
        agent_id: Optional agent identifier for agent-scoped memory.
        metadata: Optional metadata tags for filtering.

    Returns:
        Mem0 add result with extracted memory IDs.
    """
    mem = get_memory()
    kwargs: dict[str, Any] = {"user_id": user_id}
    if agent_id:
        kwargs["agent_id"] = agent_id
    if metadata:
        kwargs["metadata"] = metadata
    result: Any = mem.add(messages, **kwargs)
    return dict(result) if isinstance(result, dict) else {"results": result}


async def search_memory(
    query: str,
    user_id: str,
    agent_id: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search semantic memory for relevant facts.

    Args:
        query: Natural language search query.
        user_id: User identifier to scope the search.
        agent_id: Optional agent identifier for agent-scoped search.
        limit: Maximum number of results to return.

    Returns:
        List of memory entries with content and relevance scores.
    """
    mem = get_memory()
    kwargs: dict[str, Any] = {"user_id": user_id, "limit": limit}
    if agent_id:
        kwargs["agent_id"] = agent_id
    results: Any = mem.search(query, **kwargs)
    if isinstance(results, dict):
        return list(results.get("results", []))
    return list(results) if results else []


async def get_user_memories(
    user_id: str,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get all memories for a user (optionally scoped to an agent).

    Args:
        user_id: User identifier.
        agent_id: Optional agent identifier.

    Returns:
        List of all stored memory entries for the user.
    """
    mem = get_memory()
    kwargs: dict[str, Any] = {"user_id": user_id}
    if agent_id:
        kwargs["agent_id"] = agent_id
    results: Any = mem.get_all(**kwargs)
    if isinstance(results, dict):
        return list(results.get("results", []))
    return list(results) if results else []
