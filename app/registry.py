"""Agent Registry: persistent storage for AgentConfig objects in PostgreSQL.

Provides async CRUD operations for saving, listing, and updating agents
created by the builder. Uses asyncpg for direct PostgreSQL access.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from app.agents.factory import AgentConfig
from app.config import settings

# ── Connection pool (lazy singleton) ─────────────────────────────────

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]

# SQL to create the table if it doesn't exist (idempotent).
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS nexus_agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    instructions    TEXT NOT NULL DEFAULT '',
    role            VARCHAR(50) NOT NULL DEFAULT 'worker',
    include_todo        BOOLEAN NOT NULL DEFAULT TRUE,
    include_filesystem  BOOLEAN NOT NULL DEFAULT FALSE,
    include_subagents   BOOLEAN NOT NULL DEFAULT FALSE,
    include_skills      BOOLEAN NOT NULL DEFAULT FALSE,
    include_memory      BOOLEAN NOT NULL DEFAULT FALSE,
    include_web         BOOLEAN NOT NULL DEFAULT FALSE,
    context_manager     BOOLEAN NOT NULL DEFAULT TRUE,
    token_limit     INTEGER,
    cost_budget_usd DOUBLE PRECISION,
    status          VARCHAR(50) NOT NULL DEFAULT 'ready',
    total_runs      INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_run_at     TIMESTAMP WITH TIME ZONE
);
"""


async def _get_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    """Return the connection pool, creating it and the table on first call."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)
    return _pool


# ── CRUD operations ──────────────────────────────────────────────────


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record to a plain dict with serializable values."""
    d: dict[str, Any] = dict(row)
    # Convert UUID and datetime to strings for JSON serialization
    if isinstance(d.get("id"), uuid.UUID):
        d["id"] = str(d["id"])
    for key in ("created_at", "last_run_at"):
        if isinstance(d.get(key), datetime):
            d[key] = d[key].isoformat()
    return d


async def save_agent(config: AgentConfig) -> dict[str, Any]:
    """Save an AgentConfig to the registry and return the stored record.

    Args:
        config: The AgentConfig produced by the builder agent.

    Returns:
        Dict with the saved agent record including generated id and timestamps.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO nexus_agents (
                name, description, instructions, role,
                include_todo, include_filesystem, include_subagents,
                include_skills, include_memory, include_web, context_manager,
                token_limit, cost_budget_usd
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *
            """,
            config.name,
            config.description,
            config.instructions,
            config.role,
            config.include_todo,
            config.include_filesystem,
            config.include_subagents,
            config.include_skills,
            config.include_memory,
            config.include_web,
            config.context_manager,
            config.token_limit,
            config.cost_budget_usd,
        )
    if row is None:
        msg = "Failed to insert agent"
        raise RuntimeError(msg)
    return _row_to_dict(row)


async def get_agent(agent_id: str) -> dict[str, Any] | None:
    """Get a single agent by ID.

    Args:
        agent_id: UUID string of the agent.

    Returns:
        Agent record dict, or None if not found.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM nexus_agents WHERE id = $1",
            uuid.UUID(agent_id),
        )
    return _row_to_dict(row) if row else None


async def list_agents(limit: int = 50) -> list[dict[str, Any]]:
    """List all agents ordered by creation date (newest first).

    Args:
        limit: Maximum number of agents to return.

    Returns:
        List of agent record dicts.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM nexus_agents ORDER BY created_at DESC LIMIT $1",
            limit,
        )
    return [_row_to_dict(r) for r in rows]


async def update_agent_run_stats(
    agent_id: str,
    tokens_used: int,
) -> dict[str, Any] | None:
    """Update run statistics after an agent execution.

    Increments total_runs, adds tokens_used to total_tokens,
    and sets last_run_at to now.

    Args:
        agent_id: UUID string of the agent.
        tokens_used: Number of tokens consumed in this run.

    Returns:
        Updated agent record dict, or None if not found.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE nexus_agents
            SET total_runs = total_runs + 1,
                total_tokens = total_tokens + $2,
                last_run_at = $3,
                status = 'ready'
            WHERE id = $1
            RETURNING *
            """,
            uuid.UUID(agent_id),
            tokens_used,
            datetime.now(timezone.utc),
        )
    return _row_to_dict(row) if row else None


async def agent_config_from_record(record: dict[str, Any]) -> AgentConfig:
    """Reconstruct an AgentConfig from a registry record.

    Args:
        record: Agent record dict from the registry.

    Returns:
        AgentConfig ready to pass to build_agent().
    """
    return AgentConfig(
        name=record["name"],
        description=record["description"],
        instructions=record["instructions"],
        role=record["role"],
        include_todo=record["include_todo"],
        include_filesystem=record["include_filesystem"],
        include_subagents=record["include_subagents"],
        include_skills=record["include_skills"],
        include_memory=record["include_memory"],
        include_web=record["include_web"],
        context_manager=record["context_manager"],
        token_limit=record.get("token_limit"),
        cost_budget_usd=record.get("cost_budget_usd"),
    )
