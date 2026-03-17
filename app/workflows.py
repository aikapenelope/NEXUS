"""Workflow engine: sequential agent pipelines with HITL approval.

Provides CRUD for workflow definitions and a runner that executes
agents in sequence, passing each agent's output as the next agent's input.
Steps can require human approval before proceeding to the next step.
"""

from __future__ import annotations

import json as _json
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
    last_run_at TIMESTAMP WITH TIME ZONE,
    pending_state JSONB
);
"""

_ENSURE_PENDING_STATE_COL = """
ALTER TABLE nexus_workflows
ADD COLUMN IF NOT EXISTS pending_state JSONB;
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
            await conn.execute(_ENSURE_PENDING_STATE_COL)
    return _pool


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record to a JSON-serializable dict."""
    d: dict[str, Any] = dict(row)
    if isinstance(d.get("id"), uuid.UUID):
        d["id"] = str(d["id"])
    for key in ("created_at", "last_run_at"):
        if isinstance(d.get(key), datetime):
            d[key] = d[key].isoformat()
    # Parse JSONB fields that asyncpg may return as strings
    for jkey in ("steps", "pending_state"):
        if isinstance(d.get(jkey), str):
            d[jkey] = _json.loads(d[jkey])
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
            _json.dumps(steps),
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


async def _execute_steps(
    workflow_id: str,
    workflow_name: str,
    steps: list[dict[str, Any]],
    current_input: str,
    start_index: int = 0,
    prior_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run workflow steps starting from *start_index*.

    If a step has ``requires_approval: true``, execution pauses after
    that step completes.  The workflow status is set to
    ``awaiting_approval`` and the partial state is persisted so it can
    be resumed via :func:`approve_workflow`.

    Returns the standard workflow-run result dict.  When paused, the
    ``status`` key is ``"awaiting_approval"`` and ``pending_step`` shows
    which step is waiting.
    """
    step_results: list[dict[str, Any]] = list(prior_results or [])

    for i in range(start_index, len(steps)):
        step = steps[i]
        agent_name = step.get("agent_name", "")
        if not agent_name:
            msg = f"Step {i} has no agent_name"
            raise ValueError(msg)

        record = await _resolve_agent(agent_name)
        config = await agent_config_from_record(record)
        agent_id = record["id"]

        template = step.get("prompt_template", "{input}")
        prompt = template.replace("{input}", current_input)

        t0 = time.monotonic()
        result = await run_deep_agent(config, prompt)
        latency = int((time.monotonic() - t0) * 1000)
        usage = result.get("usage", {})
        output = result["output"]

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

        current_input = output

        # ── HITL: pause if this step requires approval ───────────
        needs_approval = step.get("requires_approval", False)
        has_more_steps = i < len(steps) - 1
        if needs_approval and has_more_steps:
            pending = {
                "next_step_index": i + 1,
                "current_input": current_input,
                "step_results": step_results,
                "initial_input": current_input,
            }
            pool = await _get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE nexus_workflows
                    SET status = 'awaiting_approval',
                        pending_state = $2::jsonb
                    WHERE id = $1
                    """,
                    uuid.UUID(workflow_id),
                    _json.dumps(pending),
                )
            return {
                "workflow_id": workflow_id,
                "workflow_name": workflow_name,
                "steps": step_results,
                "final_output": current_input,
                "total_steps": len(step_results),
                "status": "awaiting_approval",
                "pending_step": i + 1,
            }

    # ── All steps completed ──────────────────────────────────────
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE nexus_workflows
            SET total_runs = total_runs + 1,
                last_run_at = $2,
                status = 'ready',
                pending_state = NULL
            WHERE id = $1
            """,
            uuid.UUID(workflow_id),
            datetime.now(timezone.utc),
        )

    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "steps": step_results,
        "final_output": current_input,
        "total_steps": len(step_results),
        "status": "completed",
    }


async def run_workflow(
    workflow_id: str,
    initial_input: str,
) -> dict[str, Any]:
    """Execute a workflow: run each step's agent sequentially.

    The output of each agent becomes the input prompt for the next.
    Steps can define a ``prompt_template`` with ``{input}`` placeholder;
    if omitted, the raw previous output is used as the prompt.

    Steps with ``requires_approval: true`` will pause execution after
    completing, requiring a call to :func:`approve_workflow` to continue.

    Args:
        workflow_id: UUID of the workflow to run.
        initial_input: The starting prompt for the first agent.

    Returns:
        Dict with ``steps``, ``final_output``, and ``status``.
    """
    workflow = await get_workflow(workflow_id)
    if workflow is None:
        msg = f"Workflow '{workflow_id}' not found"
        raise ValueError(msg)

    steps: list[dict[str, Any]] = workflow.get("steps", [])
    if not steps:
        msg = "Workflow has no steps defined"
        raise ValueError(msg)

    if workflow.get("status") == "awaiting_approval":
        msg = "Workflow is awaiting approval. Approve or reject before re-running."
        raise ValueError(msg)

    # Reset any stale pending state
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE nexus_workflows
            SET status = 'running', pending_state = NULL
            WHERE id = $1
            """,
            uuid.UUID(workflow_id),
        )

    return await _execute_steps(
        workflow_id=workflow_id,
        workflow_name=workflow["name"],
        steps=steps,
        current_input=initial_input,
    )


# ── HITL: approve / reject ───────────────────────────────────────────


async def approve_workflow(workflow_id: str) -> dict[str, Any]:
    """Approve a paused workflow and resume execution from the next step.

    Returns the workflow-run result dict (may pause again if a later
    step also requires approval).
    """
    workflow = await get_workflow(workflow_id)
    if workflow is None:
        msg = f"Workflow '{workflow_id}' not found"
        raise ValueError(msg)

    if workflow.get("status") != "awaiting_approval":
        msg = "Workflow is not awaiting approval"
        raise ValueError(msg)

    pending = workflow.get("pending_state")
    if not pending or not isinstance(pending, dict):
        msg = "No pending state found for workflow"
        raise ValueError(msg)

    next_index: int = pending["next_step_index"]
    current_input: str = pending["current_input"]
    prior_results: list[dict[str, Any]] = pending.get("step_results", [])
    steps: list[dict[str, Any]] = workflow.get("steps", [])

    # Mark as running while we resume
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE nexus_workflows
            SET status = 'running', pending_state = NULL
            WHERE id = $1
            """,
            uuid.UUID(workflow_id),
        )

    return await _execute_steps(
        workflow_id=workflow_id,
        workflow_name=workflow["name"],
        steps=steps,
        current_input=current_input,
        start_index=next_index,
        prior_results=prior_results,
    )


async def reject_workflow(workflow_id: str, reason: str = "") -> dict[str, Any]:
    """Reject a paused workflow, cancelling remaining steps.

    Returns the partial results collected before the rejection.
    """
    workflow = await get_workflow(workflow_id)
    if workflow is None:
        msg = f"Workflow '{workflow_id}' not found"
        raise ValueError(msg)

    if workflow.get("status") != "awaiting_approval":
        msg = "Workflow is not awaiting approval"
        raise ValueError(msg)

    pending = workflow.get("pending_state")
    prior_results: list[dict[str, Any]] = (
        pending.get("step_results", []) if isinstance(pending, dict) else []
    )
    last_output = (
        pending.get("current_input", "") if isinstance(pending, dict) else ""
    )

    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE nexus_workflows
            SET status = 'ready',
                pending_state = NULL,
                total_runs = total_runs + 1,
                last_run_at = $2
            WHERE id = $1
            """,
            uuid.UUID(workflow_id),
            datetime.now(timezone.utc),
        )

    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow["name"],
        "steps": prior_results,
        "final_output": last_output,
        "total_steps": len(prior_results),
        "status": "rejected",
        "rejection_reason": reason,
    }
