"""Evaluation framework for NEXUS agents.

Runs test cases against saved agents and scores results using
pluggable evaluators: exact_match, contains, and llm_judge.
"""

from __future__ import annotations

import json as _json
import uuid
from datetime import datetime
from typing import Any

import asyncpg

from app.agents.factory import AgentConfig, run_deep_agent
from app.config import settings
from app.registry import agent_config_from_record, get_agent

# ── Connection pool ──────────────────────────────────────────────────

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS nexus_evals (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id    UUID NOT NULL,
    agent_name  VARCHAR(255) NOT NULL,
    dataset     JSONB NOT NULL DEFAULT '[]',
    results     JSONB NOT NULL DEFAULT '[]',
    scores      JSONB NOT NULL DEFAULT '{}',
    status      VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
"""


async def _get_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    global _pool  # noqa: PLW0603
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url, min_size=1, max_size=3
        )
        async with _pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)
    return _pool


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    d: dict[str, Any] = dict(row)
    for key in ("id", "agent_id"):
        if isinstance(d.get(key), uuid.UUID):
            d[key] = str(d[key])
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].isoformat()
    for key in ("dataset", "results", "scores"):
        if isinstance(d.get(key), str):
            d[key] = _json.loads(d[key])
    return d


# ── Evaluators ───────────────────────────────────────────────────────


def _eval_exact_match(output: str, expected: str) -> float:
    """1.0 if output matches expected exactly (case-insensitive), else 0.0."""
    return 1.0 if output.strip().lower() == expected.strip().lower() else 0.0


def _eval_contains(output: str, expected: str) -> float:
    """1.0 if expected substring is found in output (case-insensitive)."""
    return 1.0 if expected.strip().lower() in output.strip().lower() else 0.0


async def _eval_llm_judge(output: str, expected: str, prompt: str) -> float:
    """Use an LLM to judge output quality on a 0-1 scale.

    Falls back to contains if the LLM call fails.
    """
    try:
        from pydantic_ai import Agent

        judge = Agent(
            model=settings.haiku_model,
            system_prompt=(
                "You are an evaluation judge. Score the agent's output on a scale "
                "from 0.0 to 1.0 based on how well it answers the prompt and matches "
                "the expected output. Respond with ONLY a number between 0.0 and 1.0."
            ),
        )
        judge_prompt = (
            f"Prompt: {prompt}\n\n"
            f"Expected output: {expected}\n\n"
            f"Actual output: {output}\n\n"
            "Score (0.0 to 1.0):"
        )
        result = await judge.run(judge_prompt)
        score_text = result.output.strip()
        return max(0.0, min(1.0, float(score_text)))
    except Exception:
        # Fallback to contains
        return _eval_contains(output, expected)


EVALUATORS: dict[str, str] = {
    "exact_match": "Exact string match (case-insensitive)",
    "contains": "Expected text found in output (case-insensitive)",
    "llm_judge": "LLM-based quality scoring (0.0-1.0)",
}


async def _run_evaluator(
    evaluator: str, output: str, expected: str, prompt: str
) -> float:
    """Dispatch to the appropriate evaluator function."""
    if evaluator == "exact_match":
        return _eval_exact_match(output, expected)
    if evaluator == "contains":
        return _eval_contains(output, expected)
    if evaluator == "llm_judge":
        return await _eval_llm_judge(output, expected, prompt)
    msg = f"Unknown evaluator: {evaluator}"
    raise ValueError(msg)


# ── Run evaluation ───────────────────────────────────────────────────


async def run_eval(
    agent_id: str,
    dataset: list[dict[str, str]],
    evaluator: str = "contains",
) -> dict[str, Any]:
    """Run an evaluation suite against a saved agent.

    Args:
        agent_id: UUID of the agent to evaluate.
        dataset: List of test cases, each with "prompt" and "expected" keys.
        evaluator: Evaluator to use (exact_match, contains, llm_judge).

    Returns:
        The saved evaluation record with results and scores.
    """
    # Load agent
    agent_record = await get_agent(agent_id)
    if agent_record is None:
        msg = f"Agent {agent_id} not found"
        raise ValueError(msg)

    config: AgentConfig = await agent_config_from_record(agent_record)
    agent_name = agent_record.get("name", "unknown")

    # Create eval record (status=running)
    pool = await _get_pool()
    async with pool.acquire() as conn:
        eval_row = await conn.fetchrow(
            """
            INSERT INTO nexus_evals (agent_id, agent_name, dataset, status)
            VALUES ($1, $2, $3::jsonb, 'running')
            RETURNING *
            """,
            uuid.UUID(agent_id),
            agent_name,
            _json.dumps(dataset),
        )
    assert eval_row is not None
    eval_id = eval_row["id"]

    # Run each test case
    results: list[dict[str, Any]] = []
    total_score = 0.0

    for case in dataset:
        prompt = case.get("prompt", "")
        expected = case.get("expected", "")
        try:
            agent_output = await run_deep_agent(config, prompt)
            output_text = str(agent_output.get("output", ""))
            score = await _run_evaluator(evaluator, output_text, expected, prompt)
            results.append({
                "prompt": prompt,
                "expected": expected,
                "output": output_text,
                "score": score,
                "status": "completed",
            })
            total_score += score
        except Exception as e:
            results.append({
                "prompt": prompt,
                "expected": expected,
                "output": "",
                "score": 0.0,
                "status": "error",
                "error": str(e),
            })

    # Compute aggregate scores
    n = len(results)
    avg_score = total_score / n if n > 0 else 0.0
    pass_count = sum(1 for r in results if r["score"] >= 0.5)
    scores = {
        "evaluator": evaluator,
        "avg_score": round(avg_score, 3),
        "pass_rate": round(pass_count / n * 100, 1) if n > 0 else 0.0,
        "total_cases": n,
        "passed": pass_count,
        "failed": n - pass_count,
    }

    # Update eval record
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE nexus_evals
            SET results = $1::jsonb, scores = $2::jsonb, status = 'completed'
            WHERE id = $3
            RETURNING *
            """,
            _json.dumps(results),
            _json.dumps(scores),
            eval_id,
        )
    assert row is not None
    return _row_to_dict(row)


# ── Read ─────────────────────────────────────────────────────────────


async def list_evals(
    agent_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    """List evaluations for an agent, newest first."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM nexus_evals
            WHERE agent_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            uuid.UUID(agent_id),
            limit,
        )
    return [_row_to_dict(r) for r in rows]


async def get_eval(eval_id: str) -> dict[str, Any] | None:
    """Get a single evaluation by ID."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM nexus_evals WHERE id = $1",
            uuid.UUID(eval_id),
        )
    return _row_to_dict(row) if row else None
