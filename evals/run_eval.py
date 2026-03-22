"""NEXUS Eval Suite: measure coding agent quality on real tasks.

Runs 5 tasks of increasing difficulty against the NEXUS repo via
POST /tasks/code, then validates the results.

Usage:
    python evals/run_eval.py                    # run all tasks
    python evals/run_eval.py --task type-hints  # run one task
    python evals/run_eval.py --api http://host:8000  # custom API URL
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

REPO_URL = "https://github.com/aikapenelope/NEXUS.git"
DEFAULT_API = "http://localhost:8000"

# ── Task definitions ─────────────────────────────────────────────────

TASKS = [
    {
        "id": "type-hints",
        "difficulty": "easy",
        "task": (
            "Add complete type hints to app/tasks.py. "
            "Every function parameter and return type must be annotated. "
            "Do not change any logic, only add type annotations."
        ),
        "token_limit": 100000,
        "cost_budget": 0.50,
        "validation_cmd": ["python3", "-m", "pyright", "app/tasks.py"],
    },
    {
        "id": "write-tests",
        "difficulty": "medium",
        "task": (
            "Write pytest tests for app/sessions.py. "
            "Test SessionManager: create, get, get_or_create, remove, "
            "list_sessions, cleanup_idle. Save to tests/test_sessions.py."
        ),
        "token_limit": 100000,
        "cost_budget": 0.50,
        "validation_cmd": ["python3", "-m", "pytest", "tests/test_sessions.py", "-v"],
    },
    {
        "id": "fix-lint",
        "difficulty": "medium",
        "task": (
            "Fix all ruff lint errors in app/. "
            "Run 'ruff check app/' and fix every error. "
            "Do not change functionality, only fix lint issues."
        ),
        "token_limit": 100000,
        "cost_budget": 0.50,
        "validation_cmd": ["python3", "-m", "ruff", "check", "app/"],
    },
    {
        "id": "health-endpoint",
        "difficulty": "hard",
        "task": (
            "Add a GET /health/detailed endpoint to app/main.py that returns "
            "JSON with: api_status, database_status (check asyncpg pool), "
            "redis_status (check redis ping), uptime_seconds. "
            "Import what you need. Make it async."
        ),
        "token_limit": 100000,
        "cost_budget": 0.60,
        "validation_cmd": ["python3", "-m", "pyright", "app/main.py"],
    },
    {
        "id": "refactor-tools",
        "difficulty": "hard",
        "task": (
            "Refactor app/tools/ to add a create_all_toolsets() function in "
            "app/tools/__init__.py that imports and calls all create_*_toolset "
            "functions. Return a list of non-None toolsets. "
            "Update app/agents/factory.py to use create_all_toolsets() "
            "instead of calling each factory individually."
        ),
        "token_limit": 120000,
        "cost_budget": 0.80,
        "validation_cmd": ["python3", "-m", "pyright", "app/"],
    },
]


# ── Result dataclass ─────────────────────────────────────────────────


@dataclass
class EvalResult:
    task_id: str
    difficulty: str
    status: str  # pass, fail, partial, error
    tokens_used: int
    cost_usd: float
    duration_seconds: float
    files_changed: list[str]
    diff_lines: int
    validation_passed: bool
    agent_output: str
    error: str | None = None


# ── Runner ───────────────────────────────────────────────────────────


def run_task(task: dict, api_url: str) -> EvalResult:
    """Run a single eval task via POST /tasks/code."""
    start = time.time()

    try:
        with httpx.Client(timeout=300) as client:
            resp = client.post(
                f"{api_url}/tasks/code",
                json={
                    "repo_url": REPO_URL,
                    "task": task["task"],
                    "branch": "main",
                    "agent": "nexus-developer",
                    "token_limit": task["token_limit"],
                    "cost_budget_usd": task["cost_budget"],
                },
            )
    except Exception as e:
        return EvalResult(
            task_id=task["id"],
            difficulty=task["difficulty"],
            status="error",
            tokens_used=0,
            cost_usd=0,
            duration_seconds=time.time() - start,
            files_changed=[],
            diff_lines=0,
            validation_passed=False,
            agent_output="",
            error=str(e),
        )

    duration = time.time() - start

    if resp.status_code != 200:
        return EvalResult(
            task_id=task["id"],
            difficulty=task["difficulty"],
            status="error",
            tokens_used=0,
            cost_usd=0,
            duration_seconds=duration,
            files_changed=[],
            diff_lines=0,
            validation_passed=False,
            agent_output="",
            error=resp.text[:500],
        )

    result = resp.json()
    tokens = result.get("tokens_used", 0)
    # Approximate cost: Haiku ~$0.80/1M input + $4/1M output, rough avg $3/1M
    cost = tokens * 3.0 / 1_000_000

    diff_lines = len(result.get("diff", "").split("\n"))
    files = result.get("files_changed", [])

    # Run validation in the session workspace
    session_id = result.get("session_id", "")
    workspace = f"/opt/nexus/data/sessions/{session_id}/workspace"
    validation_passed = False

    if task.get("validation_cmd"):
        try:
            val = subprocess.run(
                task["validation_cmd"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=30,
            )
            validation_passed = val.returncode == 0
        except Exception:
            validation_passed = False

    status = "pass" if validation_passed else ("partial" if files else "fail")

    return EvalResult(
        task_id=task["id"],
        difficulty=task["difficulty"],
        status=status,
        tokens_used=tokens,
        cost_usd=round(cost, 4),
        duration_seconds=round(duration, 1),
        files_changed=files,
        diff_lines=diff_lines,
        validation_passed=validation_passed,
        agent_output=result.get("output", "")[:200],
    )


# ── Output ───────────────────────────────────────────────────────────


def print_results(results: list[EvalResult]) -> None:
    """Print results as a formatted table."""
    print()
    print("NEXUS Eval Suite")
    print("=" * 72)
    print(f"{'Task':<20} {'Diff':<6} {'Status':<8} {'Tokens':>8} {'Cost':>8} {'Time':>6}")
    print("-" * 72)

    total_tokens = 0
    total_cost = 0.0
    passed = 0

    for r in results:
        total_tokens += r.tokens_used
        total_cost += r.cost_usd
        if r.status == "pass":
            passed += 1

        status_icon = {"pass": "PASS", "fail": "FAIL", "partial": "PART", "error": "ERR"}
        print(
            f"{r.task_id:<20} {r.difficulty:<6} "
            f"{status_icon.get(r.status, '?'):<8} "
            f"{r.tokens_used:>8,} "
            f"${r.cost_usd:>6.3f} "
            f"{r.duration_seconds:>5.0f}s"
        )
        if r.error:
            print(f"  ERROR: {r.error[:80]}")

    print("-" * 72)
    print(
        f"{'Total':<20} {'':6} "
        f"{passed}/{len(results):<6} "
        f"{total_tokens:>8,} "
        f"${total_cost:>6.3f} "
    )
    print(f"Pass rate: {passed}/{len(results)} ({100*passed//max(len(results),1)}%)")
    print()


def save_results(results: list[EvalResult], path: Path) -> None:
    """Save results to JSON file."""
    data = [asdict(r) for r in results]
    path.write_text(json.dumps(data, indent=2, default=str))
    print(f"Results saved to {path}")


# ── Main ─────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="NEXUS Eval Suite")
    parser.add_argument("--task", help="Run a specific task by ID")
    parser.add_argument("--api", default=DEFAULT_API, help="API base URL")
    parser.add_argument("--output", default="evals/results.json", help="Output file")
    args = parser.parse_args()

    tasks = TASKS
    if args.task:
        tasks = [t for t in TASKS if t["id"] == args.task]
        if not tasks:
            print(f"Task '{args.task}' not found. Available: {[t['id'] for t in TASKS]}")
            sys.exit(1)

    print(f"Running {len(tasks)} eval tasks against {args.api}")
    print()

    results = []
    for task in tasks:
        print(f"Running: {task['id']} ({task['difficulty']})...", flush=True)
        result = run_task(task, args.api)
        results.append(result)
        print(f"  -> {result.status} ({result.tokens_used:,} tokens, {result.duration_seconds}s)")

    print_results(results)
    save_results(results, Path(args.output))


if __name__ == "__main__":
    main()
