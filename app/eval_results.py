"""Eval results storage and API endpoint.

Stores eval results in nexus_evals table and provides GET /evals/results.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evals", tags=["evals"])

RESULTS_FILE = Path("evals/results.json")


@router.get("/results")
async def get_eval_results() -> dict[str, Any]:
    """Get the latest eval results.

    Reads from evals/results.json (written by run_eval.py).
    """
    if not RESULTS_FILE.exists():
        return {"results": [], "summary": {"total": 0, "passed": 0, "pass_rate": 0}}

    try:
        data = json.loads(RESULTS_FILE.read_text())
    except Exception:
        return {"results": [], "summary": {"total": 0, "passed": 0, "pass_rate": 0}}

    passed = sum(1 for r in data if r.get("status") == "pass")
    total = len(data)

    return {
        "results": data,
        "summary": {
            "total": total,
            "passed": passed,
            "pass_rate": round(passed / max(total, 1) * 100, 1),
            "total_tokens": sum(r.get("tokens_used", 0) for r in data),
            "total_cost": round(sum(r.get("cost_usd", 0) for r in data), 4),
        },
    }
