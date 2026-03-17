"""Conversation persistence: stores chat history in PostgreSQL.

Provides async CRUD for conversations and messages, following the same
raw-SQL + asyncpg pattern used by registry.py and workflows.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from app.config import settings

# ── Connection pool (lazy singleton) ─────────────────────────────────

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS nexus_conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       VARCHAR(255),
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nexus_messages (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id   UUID NOT NULL REFERENCES nexus_conversations(id) ON DELETE CASCADE,
    role              VARCHAR(20) NOT NULL,
    content           TEXT NOT NULL DEFAULT '',
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON nexus_messages (conversation_id, created_at ASC);
"""


async def _get_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    """Return the connection pool, creating tables on first call."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(_CREATE_TABLES_SQL)
    return _pool


# ── Helpers ──────────────────────────────────────────────────────────


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record to a JSON-serializable dict."""
    d: dict[str, Any] = dict(row)
    for key in ("id", "conversation_id"):
        if isinstance(d.get(key), uuid.UUID):
            d[key] = str(d[key])
    for key in ("created_at", "updated_at"):
        if isinstance(d.get(key), datetime):
            d[key] = d[key].isoformat()
    return d


# ── Conversation CRUD ────────────────────────────────────────────────


async def create_conversation(title: str | None = None) -> dict[str, Any]:
    """Create a new conversation.

    Args:
        title: Optional title. If omitted, can be set later (e.g. from
               the first user message).

    Returns:
        The created conversation record.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO nexus_conversations (title) VALUES ($1) RETURNING *",
            title,
        )
    if row is None:
        msg = "Failed to create conversation"
        raise RuntimeError(msg)
    return _row_to_dict(row)


async def list_conversations(limit: int = 50) -> list[dict[str, Any]]:
    """List conversations ordered by most recently updated.

    Args:
        limit: Maximum number of conversations to return.

    Returns:
        List of conversation dicts.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.*,
                   (SELECT COUNT(*)::int FROM nexus_messages WHERE conversation_id = c.id)
                       AS message_count
            FROM nexus_conversations c
            ORDER BY c.updated_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [_row_to_dict(r) for r in rows]


async def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    """Get a single conversation by ID.

    Args:
        conversation_id: UUID string.

    Returns:
        Conversation dict or None.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM nexus_conversations WHERE id = $1",
            uuid.UUID(conversation_id),
        )
    return _row_to_dict(row) if row else None


async def update_conversation_title(
    conversation_id: str, title: str
) -> dict[str, Any] | None:
    """Update a conversation's title.

    Args:
        conversation_id: UUID string.
        title: New title.

    Returns:
        Updated conversation dict or None.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE nexus_conversations
            SET title = $2, updated_at = $3
            WHERE id = $1
            RETURNING *
            """,
            uuid.UUID(conversation_id),
            title,
            datetime.now(timezone.utc),
        )
    return _row_to_dict(row) if row else None


async def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation and all its messages (CASCADE).

    Args:
        conversation_id: UUID string.

    Returns:
        True if deleted, False if not found.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM nexus_conversations WHERE id = $1",
            uuid.UUID(conversation_id),
        )
    return result == "DELETE 1"


# ── Message CRUD ─────────────────────────────────────────────────────


async def add_message(
    conversation_id: str,
    role: str,
    content: str,
) -> dict[str, Any]:
    """Add a message to a conversation.

    Also bumps the conversation's updated_at timestamp.

    Args:
        conversation_id: UUID string of the parent conversation.
        role: "user", "assistant", or "system".
        content: Message text.

    Returns:
        The created message record.
    """
    pool = await _get_pool()
    cid = uuid.UUID(conversation_id)
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO nexus_messages (conversation_id, role, content, created_at)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            cid,
            role,
            content,
            now,
        )
        # Bump conversation updated_at
        await conn.execute(
            "UPDATE nexus_conversations SET updated_at = $2 WHERE id = $1",
            cid,
            now,
        )
    if row is None:
        msg = "Failed to insert message"
        raise RuntimeError(msg)
    return _row_to_dict(row)


async def get_messages(
    conversation_id: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Get messages for a conversation in chronological order.

    Args:
        conversation_id: UUID string.
        limit: Maximum messages to return.

    Returns:
        List of message dicts ordered by created_at ASC.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM nexus_messages
            WHERE conversation_id = $1
            ORDER BY created_at ASC
            LIMIT $2
            """,
            uuid.UUID(conversation_id),
            limit,
        )
    return [_row_to_dict(r) for r in rows]
