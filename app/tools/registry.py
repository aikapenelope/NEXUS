"""Tool Registry: catalog of available tools for NEXUS agents.

Provides a static catalog of tools organized by category, plus a
database-backed configuration store for tools that need API keys
or other settings.
"""

from __future__ import annotations

import json as _json
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from app.config import settings

# ── Tool catalog ─────────────────────────────────────────────────────
# Each tool has: id, name, description, category, requires_config (bool),
# config_fields (list of field names needed), and built_in (bool).

TOOL_CATALOG: list[dict[str, Any]] = [
    # ── Search ───────────────────────────────────────────────────
    {
        "id": "duckduckgo_search",
        "name": "DuckDuckGo Search",
        "description": "Web search via DuckDuckGo (no API key needed)",
        "category": "Search",
        "requires_config": False,
        "config_fields": [],
        "built_in": True,
    },
    {
        "id": "tavily_search",
        "name": "Tavily Search",
        "description": "AI-optimized web search with structured results",
        "category": "Search",
        "requires_config": True,
        "config_fields": ["api_key"],
        "built_in": True,
    },
    {
        "id": "exa_search",
        "name": "Exa Search",
        "description": "Neural search engine for finding similar content",
        "category": "Search",
        "requires_config": True,
        "config_fields": ["api_key"],
        "built_in": True,
    },
    # ── Web ───────────────────────────────────────────────────────
    {
        "id": "web_browse",
        "name": "Web Browser",
        "description": "Browse web pages and extract content (via Playwright MCP)",
        "category": "Web",
        "requires_config": False,
        "config_fields": [],
        "built_in": True,
    },
    # ── Data ──────────────────────────────────────────────────────
    {
        "id": "memory_search",
        "name": "Semantic Memory",
        "description": "Search and store facts in vector memory (Mem0 + pgvector)",
        "category": "Data",
        "requires_config": False,
        "config_fields": [],
        "built_in": True,
    },
    {
        "id": "sql_query",
        "name": "SQL Query",
        "description": "Execute read-only SQL queries against a PostgreSQL database",
        "category": "Data",
        "requires_config": True,
        "config_fields": ["database_url"],
        "built_in": False,
    },
    # ── Communication ─────────────────────────────────────────────
    {
        "id": "email_send",
        "name": "Email Sender",
        "description": "Send emails via SMTP",
        "category": "Communication",
        "requires_config": True,
        "config_fields": ["smtp_host", "smtp_port", "smtp_user", "smtp_password"],
        "built_in": False,
    },
    {
        "id": "slack_notify",
        "name": "Slack Notification",
        "description": "Send messages to Slack channels via webhook",
        "category": "Communication",
        "requires_config": True,
        "config_fields": ["webhook_url"],
        "built_in": False,
    },
    # ── Files ─────────────────────────────────────────────────────
    {
        "id": "file_read",
        "name": "File Reader",
        "description": "Read files from the local filesystem sandbox",
        "category": "Files",
        "requires_config": False,
        "config_fields": [],
        "built_in": True,
    },
    {
        "id": "file_write",
        "name": "File Writer",
        "description": "Write files to the local filesystem sandbox",
        "category": "Files",
        "requires_config": False,
        "config_fields": [],
        "built_in": True,
    },
    # ── MCP ───────────────────────────────────────────────────────
    {
        "id": "mcp_playwright",
        "name": "Playwright Browser",
        "description": "Browser automation via Playwright MCP server",
        "category": "MCP",
        "requires_config": False,
        "config_fields": [],
        "built_in": True,
    },
    {
        "id": "mcp_custom",
        "name": "Custom MCP Server",
        "description": "Connect to any MCP-compatible tool server",
        "category": "MCP",
        "requires_config": True,
        "config_fields": ["server_url"],
        "built_in": False,
    },
]

# Index by ID for fast lookup
_CATALOG_BY_ID: dict[str, dict[str, Any]] = {t["id"]: t for t in TOOL_CATALOG}

# Categories
TOOL_CATEGORIES: list[str] = sorted(
    {t["category"] for t in TOOL_CATALOG}
)


def list_catalog(category: str | None = None) -> list[dict[str, Any]]:
    """Return the full tool catalog, optionally filtered by category."""
    if category:
        return [t for t in TOOL_CATALOG if t["category"] == category]
    return list(TOOL_CATALOG)


def get_catalog_tool(tool_id: str) -> dict[str, Any] | None:
    """Get a single tool from the catalog by ID."""
    return _CATALOG_BY_ID.get(tool_id)


# ── Database: tool configurations ────────────────────────────────────

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS nexus_tool_configs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id     VARCHAR(100) NOT NULL UNIQUE,
    config      JSONB NOT NULL DEFAULT '{}',
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
"""


async def _get_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    """Return the connection pool, creating the table on first call."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url, min_size=1, max_size=3
        )
        async with _pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)
    return _pool


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record to a JSON-serializable dict."""
    d: dict[str, Any] = dict(row)
    if isinstance(d.get("id"), uuid.UUID):
        d["id"] = str(d["id"])
    for key in ("created_at", "updated_at"):
        if isinstance(d.get(key), datetime):
            d[key] = d[key].isoformat()
    if isinstance(d.get("config"), str):
        d["config"] = _json.loads(d["config"])
    return d


async def get_tool_config(tool_id: str) -> dict[str, Any] | None:
    """Get the saved configuration for a tool."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM nexus_tool_configs WHERE tool_id = $1",
            tool_id,
        )
    return _row_to_dict(row) if row else None


async def save_tool_config(
    tool_id: str,
    config: dict[str, Any],
    enabled: bool = True,
) -> dict[str, Any]:
    """Save or update a tool's configuration (upsert)."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO nexus_tool_configs (tool_id, config, enabled, updated_at)
            VALUES ($1, $2::jsonb, $3, $4)
            ON CONFLICT (tool_id) DO UPDATE
            SET config = EXCLUDED.config,
                enabled = EXCLUDED.enabled,
                updated_at = EXCLUDED.updated_at
            RETURNING *
            """,
            tool_id,
            _json.dumps(config),
            enabled,
            datetime.now(timezone.utc),
        )
    assert row is not None
    return _row_to_dict(row)


async def list_tool_configs() -> list[dict[str, Any]]:
    """List all saved tool configurations."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM nexus_tool_configs ORDER BY tool_id"
        )
    return [_row_to_dict(r) for r in rows]


async def get_tools_with_status() -> list[dict[str, Any]]:
    """Return the full catalog enriched with configuration status.

    Each tool gets an extra "configured" boolean and "enabled" boolean.
    """
    configs = {c["tool_id"]: c for c in await list_tool_configs()}
    result: list[dict[str, Any]] = []
    for tool in TOOL_CATALOG:
        entry = dict(tool)
        cfg = configs.get(tool["id"])
        if cfg:
            entry["configured"] = True
            entry["enabled"] = cfg["enabled"]
        else:
            entry["configured"] = not tool["requires_config"]
            entry["enabled"] = not tool["requires_config"]
        result.append(entry)
    return result
