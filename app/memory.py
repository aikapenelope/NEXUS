"""Mem0 semantic memory service for NEXUS.

Level 3 memory: cross-agent, cross-session semantic memory backed by
PostgreSQL + pgvector for vector storage and Voyage AI for embeddings
(voyage-3-lite, 512 dims, via OpenAI-compatible API).

Uses Groq (Llama 3.3 70B) as the LLM for memory extraction/consolidation.
Free tier, no local model downloads -- all inference is via API.
"""

from __future__ import annotations

from typing import Any

from mem0 import Memory
from mem0.embeddings.openai import OpenAIEmbedding

from app.config import settings


def _patched_embed(
    self: OpenAIEmbedding,
    text: str,
    memory_action: str | None = None,
) -> list[float]:
    """Patched embed that skips ``dimensions`` for non-OpenAI backends.

    Mem0's ``OpenAIEmbedding.__init__`` forces ``embedding_dims = 1536``
    when the user doesn't set it, then ``embed()`` always passes
    ``dimensions`` to the API.  Providers like Voyage AI reject that
    parameter (Mem0 issue #4153).  This patch omits ``dimensions``
    whenever the client points at a non-OpenAI base URL.
    """
    text = text.replace("\n", " ")
    kwargs: dict[str, Any] = {"input": [text], "model": self.config.model}
    # Only send `dimensions` when talking to the real OpenAI API.
    base = getattr(self.config, "openai_base_url", "") or ""
    is_openai_native = not base or "api.openai.com" in base
    if is_openai_native and self.config.embedding_dims is not None:
        kwargs["dimensions"] = self.config.embedding_dims
    return self.client.embeddings.create(**kwargs).data[0].embedding


# Apply monkey-patch before any Memory instance is created.
OpenAIEmbedding.embed = _patched_embed  # type: ignore[assignment]

# Lazy singleton — created on first use so env vars and DB are ready.
_memory: Memory | None = None


def _get_mem0_config() -> dict[str, Any]:
    """Build the Mem0 configuration dictionary.

    - Vector store: pgvector on the same Postgres instance
    - Embedder: Voyage AI via OpenAI-compatible provider (API, no local models)
    - LLM: Groq Llama 3.3 70B for fact extraction/consolidation (free tier)
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
                "embedding_model_dims": 512,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "voyage-3-lite",
                # NOTE: Do NOT set embedding_dims here. Mem0's OpenAI embedder
                # always passes `dimensions` to the API, but Voyage AI doesn't
                # support it (known Mem0 issue #4153). voyage-3-lite natively
                # returns 512-dim vectors, matching our pgvector collection.
                "api_key": settings.voyage_api_key,
                "openai_base_url": "https://api.voyageai.com/v1",
            },
        },
        "llm": {
            "provider": "groq",
            "config": {
                "model": "llama-3.3-70b-versatile",
                "api_key": settings.groq_api_key,
                "max_tokens": 500,
                "temperature": 0.1,
                "top_p": 0.1,
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
