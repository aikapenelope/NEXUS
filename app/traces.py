"""Run history: persistent trace logging for the NEXUS dashboard.

Every agent execution (build, run, cerebro) is logged here for the
Langfuse/LangSmith-style dashboard traces view.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import asyncpg

from app.config import settings

# ── Connection pool (shared with registry) ───────────────────────────

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS nexus_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        UUID,
    agent_name      VARCHAR(255) NOT NULL DEFAULT 'anonymous',
    prompt          TEXT NOT NULL DEFAULT '',
    output          TEXT NOT NULL DEFAULT '',
    model           VARCHAR(255) NOT NULL DEFAULT '',
    role            VARCHAR(50) NOT NULL DEFAULT 'worker',
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    latency_ms      INTEGER NOT NULL DEFAULT 0,
    status          VARCHAR(50) NOT NULL DEFAULT 'completed',
    source          VARCHAR(50) NOT NULL DEFAULT 'run',
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
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


# ── Helpers ──────────────────────────────────────────────────────────


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record to a JSON-serializable dict."""
    d: dict[str, Any] = dict(row)
    if isinstance(d.get("id"), uuid.UUID):
        d["id"] = str(d["id"])
    if isinstance(d.get("agent_id"), uuid.UUID):
        d["agent_id"] = str(d["agent_id"])
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].isoformat()
    return d


# ── Write ────────────────────────────────────────────────────────────


async def save_run(
    *,
    agent_id: str | None = None,
    agent_name: str = "anonymous",
    prompt: str = "",
    output: str = "",
    model: str = "",
    role: str = "worker",
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: int = 0,
    status: str = "completed",
    source: str = "run",
) -> dict[str, Any]:
    """Log an agent execution to the run history.

    Returns the saved run record.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO nexus_runs (
                agent_id, agent_name, prompt, output, model, role,
                input_tokens, output_tokens, total_tokens,
                latency_ms, status, source
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING *
            """,
            uuid.UUID(agent_id) if agent_id else None,
            agent_name,
            prompt,
            output,
            model,
            role,
            input_tokens,
            output_tokens,
            total_tokens,
            latency_ms,
            status,
            source,
        )
    if row is None:
        msg = "Failed to insert run"
        raise RuntimeError(msg)
    return _row_to_dict(row)


# ── Read ─────────────────────────────────────────────────────────────


async def get_run(run_id: str) -> dict[str, Any] | None:
    """Get a single run by ID."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM nexus_runs WHERE id = $1",
            uuid.UUID(run_id),
        )
    return _row_to_dict(row) if row else None


async def list_runs(
    limit: int = 50,
    agent_id: str | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """List runs ordered by creation date (newest first).

    Optional filters by agent_id and source.
    """
    pool = await _get_pool()
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if agent_id:
        conditions.append(f"agent_id = ${idx}")
        params.append(uuid.UUID(agent_id))
        idx += 1

    if source:
        conditions.append(f"source = ${idx}")
        params.append(source)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM nexus_runs {where} ORDER BY created_at DESC LIMIT ${idx}",  # noqa: S608
            *params,
        )
    return [_row_to_dict(r) for r in rows]


# ── Dashboard aggregates ─────────────────────────────────────────────


async def get_dashboard_stats() -> dict[str, Any]:
    """Compute aggregate metrics for the dashboard overview.

    Returns totals, averages, time-series (last 7 days), top agents,
    and model/source breakdowns.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        # Totals
        totals = await conn.fetchrow(
            """
            SELECT
                count(*)::int AS total_runs,
                coalesce(sum(total_tokens), 0)::bigint AS total_tokens,
                coalesce(avg(latency_ms), 0)::int AS avg_latency_ms,
                coalesce(sum(input_tokens), 0)::bigint AS total_input_tokens,
                coalesce(sum(output_tokens), 0)::bigint AS total_output_tokens
            FROM nexus_runs
            """
        )

        # Agent count
        agent_count = await conn.fetchval(
            "SELECT count(*)::int FROM nexus_agents"
        )

        # Runs per day (last 7 days)
        runs_per_day = await conn.fetch(
            """
            SELECT date_trunc('day', created_at)::date AS day,
                   count(*)::int AS runs,
                   coalesce(sum(total_tokens), 0)::bigint AS tokens
            FROM nexus_runs
            WHERE created_at >= now() - interval '7 days'
            GROUP BY day ORDER BY day
            """
        )

        # Top agents by runs
        top_agents = await conn.fetch(
            """
            SELECT agent_name, count(*)::int AS runs,
                   coalesce(sum(total_tokens), 0)::bigint AS tokens,
                   coalesce(avg(latency_ms), 0)::int AS avg_latency
            FROM nexus_runs
            GROUP BY agent_name ORDER BY runs DESC LIMIT 10
            """
        )

        # Source breakdown (build, run, cerebro, copilot)
        source_breakdown = await conn.fetch(
            """
            SELECT source, count(*)::int AS runs,
                   coalesce(sum(total_tokens), 0)::bigint AS tokens
            FROM nexus_runs
            GROUP BY source ORDER BY runs DESC
            """
        )

        # Model breakdown
        model_breakdown = await conn.fetch(
            """
            SELECT model, count(*)::int AS runs,
                   coalesce(sum(total_tokens), 0)::bigint AS tokens
            FROM nexus_runs
            WHERE model != ''
            GROUP BY model ORDER BY runs DESC
            """
        )

        # Latency percentiles (p50, p95)
        latency_pcts = await conn.fetchrow(
            """
            SELECT
                coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms), 0)::int AS p50,
                coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0)::int AS p95
            FROM nexus_runs
            """
        )

        # Error rate
        error_stats = await conn.fetchrow(
            """
            SELECT
                count(*)::int AS total,
                count(*) FILTER (WHERE status = 'error')::int AS errors
            FROM nexus_runs
            """
        )

        # Tokens per hour (last 24h)
        tokens_per_hour = await conn.fetchval(
            """
            SELECT coalesce(sum(total_tokens), 0)::bigint
            FROM nexus_runs
            WHERE created_at >= now() - interval '1 hour'
            """
        )

        # Events count (from nexus_agent_events if table exists)
        try:
            events_count = await conn.fetchval(
                "SELECT count(*)::int FROM nexus_agent_events"
            )
        except asyncpg.UndefinedTableError:
            events_count = 0

    totals_dict = dict(totals) if totals else {}
    pcts = dict(latency_pcts) if latency_pcts else {}
    err = dict(error_stats) if error_stats else {}
    err_total = err.get("total", 0)
    err_count = err.get("errors", 0)
    error_rate = round(err_count / err_total * 100, 1) if err_total > 0 else 0.0

    return {
        "total_agents": agent_count or 0,
        "total_runs": totals_dict.get("total_runs", 0),
        "total_tokens": int(totals_dict.get("total_tokens", 0)),
        "total_input_tokens": int(totals_dict.get("total_input_tokens", 0)),
        "total_output_tokens": int(totals_dict.get("total_output_tokens", 0)),
        "avg_latency_ms": totals_dict.get("avg_latency_ms", 0),
        "latency_p50_ms": pcts.get("p50", 0),
        "latency_p95_ms": pcts.get("p95", 0),
        "error_rate_pct": error_rate,
        "tokens_per_hour": int(tokens_per_hour or 0),
        "total_events": events_count or 0,
        "runs_per_day": [
            {"day": str(r["day"]), "runs": r["runs"], "tokens": int(r["tokens"])}
            for r in runs_per_day
        ],
        "top_agents": [
            {
                "agent_name": r["agent_name"],
                "runs": r["runs"],
                "tokens": int(r["tokens"]),
                "avg_latency": r["avg_latency"],
            }
            for r in top_agents
        ],
        "source_breakdown": [
            {"source": r["source"], "runs": r["runs"], "tokens": int(r["tokens"])}
            for r in source_breakdown
        ],
        "model_breakdown": [
            {"model": r["model"], "runs": r["runs"], "tokens": int(r["tokens"])}
            for r in model_breakdown
        ],
    }


# ── Monitor data (combined events + runs) ────────────────────────────


async def get_monitor_data() -> dict[str, Any]:
    """Return combined monitoring data for the /dashboard/monitor page.

    Includes per-agent status, recent events, latency time-series,
    and recent runs with details.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        # Per-agent status: last run, total tokens, error count
        agent_status = await conn.fetch(
            """
            SELECT
                agent_name,
                count(*)::int AS total_runs,
                count(*) FILTER (WHERE status = 'error')::int AS error_count,
                coalesce(sum(total_tokens), 0)::bigint AS total_tokens,
                coalesce(avg(latency_ms), 0)::int AS avg_latency_ms,
                max(created_at) AS last_run_at
            FROM nexus_runs
            GROUP BY agent_name
            ORDER BY last_run_at DESC
            """
        )

        # Recent events (last 50)
        try:
            recent_events = await conn.fetch(
                """
                SELECT * FROM nexus_agent_events
                ORDER BY created_at DESC LIMIT 50
                """
            )
        except asyncpg.UndefinedTableError:
            recent_events = []

        # Latency time-series (hourly, last 24h)
        latency_series = await conn.fetch(
            """
            SELECT
                date_trunc('hour', created_at) AS hour,
                coalesce(avg(latency_ms), 0)::int AS avg_latency,
                coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms), 0)::int AS p50,
                coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0)::int AS p95,
                count(*)::int AS runs,
                coalesce(sum(total_tokens), 0)::bigint AS tokens
            FROM nexus_runs
            WHERE created_at >= now() - interval '24 hours'
            GROUP BY hour ORDER BY hour
            """
        )

        # Recent runs (last 20)
        recent_runs = await conn.fetch(
            """
            SELECT * FROM nexus_runs
            ORDER BY created_at DESC LIMIT 20
            """
        )

    def _event_to_dict(row: asyncpg.Record) -> dict[str, Any]:
        d: dict[str, Any] = dict(row)
        if isinstance(d.get("id"), uuid.UUID):
            d["id"] = str(d["id"])
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
        return d

    return {
        "agent_status": [
            {
                "agent_name": r["agent_name"],
                "total_runs": r["total_runs"],
                "error_count": r["error_count"],
                "total_tokens": int(r["total_tokens"]),
                "avg_latency_ms": r["avg_latency_ms"],
                "last_run_at": r["last_run_at"].isoformat()
                if r["last_run_at"]
                else None,
                "status": "error"
                if r["error_count"] > 0
                else "idle",
            }
            for r in agent_status
        ],
        "recent_events": [_event_to_dict(e) for e in recent_events],
        "latency_series": [
            {
                "hour": r["hour"].isoformat() if r["hour"] else None,
                "avg_latency": r["avg_latency"],
                "p50": r["p50"],
                "p95": r["p95"],
                "runs": r["runs"],
                "tokens": int(r["tokens"]),
            }
            for r in latency_series
        ],
        "recent_runs": [_row_to_dict(r) for r in recent_runs],
    }
