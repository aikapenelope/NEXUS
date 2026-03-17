"""Agent event tracking: real-time activity feed for the NEXUS dashboard.

Records granular events during agent execution (start, tool_call, complete,
error) for the live activity feed and monitoring dashboard.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import asyncpg

from app.config import settings

# ── Connection pool (lazy singleton) ─────────────────────────────────

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS nexus_agent_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name  VARCHAR(255) NOT NULL,
    run_id      UUID,
    event_type  VARCHAR(50) NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    tokens      INTEGER NOT NULL DEFAULT 0,
    latency_ms  INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_events_created
    ON nexus_agent_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_events_agent_name
    ON nexus_agent_events (agent_name, created_at DESC);
"""


async def _get_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    """Return the connection pool, creating the table on first call."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url, min_size=1, max_size=5
        )
        async with _pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)
    return _pool


# ── Helpers ──────────────────────────────────────────────────────────


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record to a JSON-serializable dict."""
    d: dict[str, Any] = dict(row)
    for key in ("id", "run_id"):
        if isinstance(d.get(key), uuid.UUID):
            d[key] = str(d[key])
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].isoformat()
    return d


# ── Write ────────────────────────────────────────────────────────────


async def emit_event(
    *,
    agent_name: str,
    event_type: str,
    detail: str = "",
    run_id: str | None = None,
    tokens: int = 0,
    latency_ms: int = 0,
) -> dict[str, Any]:
    """Record an agent activity event.

    Args:
        agent_name: Name of the agent that generated the event.
        event_type: One of 'start', 'tool_call', 'complete', 'error',
                    'approval_requested', 'approval_granted', 'approval_denied'.
        detail: Human-readable description of the event.
        run_id: Optional UUID linking to a nexus_runs record.
        tokens: Token count associated with this event (if applicable).
        latency_ms: Latency in milliseconds (if applicable).

    Returns:
        The saved event record.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO nexus_agent_events (
                agent_name, run_id, event_type, detail, tokens, latency_ms
            ) VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            agent_name,
            uuid.UUID(run_id) if run_id else None,
            event_type,
            detail,
            tokens,
            latency_ms,
        )
    if row is None:
        msg = "Failed to insert event"
        raise RuntimeError(msg)
    return _row_to_dict(row)


# ── Read ─────────────────────────────────────────────────────────────


async def list_events(
    limit: int = 50,
    agent_name: str | None = None,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    """List recent agent events, newest first.

    Args:
        limit: Maximum number of events to return.
        agent_name: Optional filter by agent name.
        event_type: Optional filter by event type.

    Returns:
        List of event dicts.
    """
    pool = await _get_pool()
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if agent_name:
        conditions.append(f"agent_name = ${idx}")
        params.append(agent_name)
        idx += 1

    if event_type:
        conditions.append(f"event_type = ${idx}")
        params.append(event_type)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM nexus_agent_events {where} ORDER BY created_at DESC LIMIT ${idx}",  # noqa: S608
            *params,
        )
    return [_row_to_dict(r) for r in rows]


async def get_event_stats() -> dict[str, Any]:
    """Get aggregate event statistics for the monitoring dashboard.

    Returns:
        Dict with event counts by type, recent activity summary, and
        per-agent event counts.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        # Event counts by type
        type_counts = await conn.fetch(
            """
            SELECT event_type, count(*)::int AS count
            FROM nexus_agent_events
            GROUP BY event_type ORDER BY count DESC
            """
        )

        # Events in last hour
        recent_count = await conn.fetchval(
            """
            SELECT count(*)::int
            FROM nexus_agent_events
            WHERE created_at >= now() - interval '1 hour'
            """
        )

        # Per-agent event counts (top 10)
        agent_counts = await conn.fetch(
            """
            SELECT agent_name, count(*)::int AS events,
                   max(created_at) AS last_event
            FROM nexus_agent_events
            GROUP BY agent_name ORDER BY events DESC LIMIT 10
            """
        )

        # Error count in last 24h
        error_count = await conn.fetchval(
            """
            SELECT count(*)::int
            FROM nexus_agent_events
            WHERE event_type = 'error'
              AND created_at >= now() - interval '24 hours'
            """
        )

    return {
        "type_counts": [
            {"event_type": r["event_type"], "count": r["count"]}
            for r in type_counts
        ],
        "recent_events_1h": recent_count or 0,
        "errors_24h": error_count or 0,
        "agent_activity": [
            {
                "agent_name": r["agent_name"],
                "events": r["events"],
                "last_event": r["last_event"].isoformat()
                if isinstance(r["last_event"], datetime)
                else str(r["last_event"]),
            }
            for r in agent_counts
        ],
    }
