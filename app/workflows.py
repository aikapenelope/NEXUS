"""Workflow engine: sequential agent pipelines.

Provides CRUD for workflow definitions and a runner that executes
agents in sequence, passing each agent's output as the next agent's input.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from app.agents.factory import run_deep_agent
from app.config import settings
from app.registry import agent_config_from_record, get_agent, list_agents
from app.traces import save_run

# ── Connection pool (lazy singleton) ─────────────────────────────────

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS nexus_workflows (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    steps       JSONB NOT NULL DEFAULT '[]',
    status      VARCHAR(50) NOT NULL DEFAULT 'ready',
    total_runs  INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_run_at TIMESTAMP WITH TIME ZONE
);
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


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record to a JSON-serializable dict."""
    import json as _json

    d: dict[str, Any] = dict(row)
    if isinstance(d.get("id"), uuid.UUID):
        d["id"] = str(d["id"])
    for key in ("created_at", "last_run_at"):
        if isinstance(d.get(key), datetime):
            d[key] = d[key].isoformat()
    # Parse JSONB fields that asyncpg may return as strings
    if isinstance(d.get("steps"), str):
        d["steps"] = _json.loads(d["steps"])
    return d


# ── CRUD ─────────────────────────────────────────────────────────────


async def save_workflow(
    name: str,
    description: str,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a new workflow definition.

    Args:
        name: Short identifier for the workflow.
        description: What the workflow does.
        steps: Ordered list of step dicts. Each step must have at least
               "agent_name" (str). Optional: "prompt_template" (str)
               with {input} placeholder for the previous step's output.

    Returns:
        The saved workflow record.
    """
    import json

    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO nexus_workflows (name, description, steps)
            VALUES ($1, $2, $3::jsonb)
            RETURNING *
            """,
            name,
            description,
            json.dumps(steps),
        )
    assert row is not None
    return _row_to_dict(row)


async def list_workflows(limit: int = 50) -> list[dict[str, Any]]:
    """List all workflow definitions."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM nexus_workflows ORDER BY created_at DESC LIMIT $1",
            limit,
        )
    return [_row_to_dict(r) for r in rows]


async def get_workflow(workflow_id: str) -> dict[str, Any] | None:
    """Get a single workflow by ID."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM nexus_workflows WHERE id = $1",
            uuid.UUID(workflow_id),
        )
    return _row_to_dict(row) if row else None


async def delete_workflow(workflow_id: str) -> bool:
    """Delete a workflow by ID."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM nexus_workflows WHERE id = $1",
            uuid.UUID(workflow_id),
        )
    return result == "DELETE 1"


# ── Execution engine ─────────────────────────────────────────────────


async def _resolve_agent(agent_name: str) -> dict[str, Any]:
    """Find an agent by name (case-insensitive) or ID.

    Raises ValueError if not found.
    """
    # Try as UUID first
    record = await get_agent(agent_name)
    if record is not None:
        return record

    # Search by name
    agents = await list_agents(limit=200)
    search = agent_name.lower()
    for a in agents:
        if a["name"].lower() == search:
            return a

    msg = f"Agent '{agent_name}' not found in registry"
    raise ValueError(msg)


async def run_workflow(
    workflow_id: str,
    initial_input: str,
) -> dict[str, Any]:
    """Execute a workflow: run each step's agent sequentially.

    The output of each agent becomes the input prompt for the next.
    Steps can define a "prompt_template" with {input} placeholder;
    if omitted, the raw previous output is used as the prompt.

    Args:
        workflow_id: UUID of the workflow to run.
        initial_input: The starting prompt for the first agent.

    Returns:
        Dict with "steps" (list of step results) and "final_output".
    """
    workflow = await get_workflow(workflow_id)
    if workflow is None:
        msg = f"Workflow '{workflow_id}' not found"
        raise ValueError(msg)

    steps: list[dict[str, Any]] = workflow.get("steps", [])
    if not steps:
        msg = "Workflow has no steps defined"
        raise ValueError(msg)

    current_input = initial_input
    step_results: list[dict[str, Any]] = []

    for i, step in enumerate(steps):
        agent_name = step.get("agent_name", "")
        if not agent_name:
            msg = f"Step {i} has no agent_name"
            raise ValueError(msg)

        # Resolve agent from registry
        record = await _resolve_agent(agent_name)
        config = await agent_config_from_record(record)
        agent_id = record["id"]

        # Build the prompt for this step
        template = step.get("prompt_template", "{input}")
        prompt = template.replace("{input}", current_input)

        # Execute the agent
        t0 = time.monotonic()
        result = await run_deep_agent(config, prompt)
        latency = int((time.monotonic() - t0) * 1000)
        usage = result.get("usage", {})
        output = result["output"]

        # Save run trace
        await save_run(
            agent_id=agent_id,
            agent_name=config.name,
            prompt=prompt[:2000],
            output=output[:2000],
            model=config.role,
            role=config.role,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency,
            source="workflow",
        )

        step_results.append(
            {
                "step": i,
                "agent_name": config.name,
                "agent_id": agent_id,
                "prompt": prompt[:500],
                "output": output,
                "latency_ms": latency,
                "tokens": usage.get("total_tokens", 0),
            }
        )

        # Pass output to next step
        current_input = output

    # Update workflow run stats
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE nexus_workflows
            SET total_runs = total_runs + 1,
                last_run_at = $2
            WHERE id = $1
            """,
            uuid.UUID(workflow_id),
            datetime.now(timezone.utc),
        )

    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow["name"],
        "steps": step_results,
        "final_output": current_input,
        "total_steps": len(step_results),
    }
