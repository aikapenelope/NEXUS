"""LSP feedback tool: runs pyright/ruff after code edits.

Gives the agent type checking and linting feedback so it can
self-correct errors without human intervention.
"""

from __future__ import annotations

import logging
import subprocess

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset
from pydantic_deep import DeepAgentDeps

logger = logging.getLogger(__name__)


def create_lsp_toolset(
    toolset_id: str = "lsp",
) -> FunctionToolset[DeepAgentDeps]:
    """Create LSP feedback tools: check_types and check_lint."""
    toolset: FunctionToolset[DeepAgentDeps] = FunctionToolset(id=toolset_id)

    @toolset.tool
    async def check_types(
        ctx: RunContext[DeepAgentDeps],
        path: str = ".",
    ) -> str:
        """Run pyright type checker on a file or directory.

        Use after editing Python files to catch type errors.
        Returns pyright output (errors, warnings) or "No errors".

        Args:
            path: File or directory to check (relative to workspace).
        """
        try:
            result = subprocess.run(
                ["python3", "-m", "pyright", path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout + result.stderr
            if result.returncode == 0:
                return "pyright: No errors found."
            return f"pyright errors:\n{output[-2000:]}"
        except FileNotFoundError:
            return "pyright not installed."
        except subprocess.TimeoutExpired:
            return "pyright timed out (>30s)."
        except Exception as e:
            return f"pyright failed: {e}"

    @toolset.tool
    async def check_lint(
        ctx: RunContext[DeepAgentDeps],
        path: str = ".",
    ) -> str:
        """Run ruff linter on a file or directory.

        Use after editing Python files to catch lint errors.
        Returns ruff output (errors) or "No errors".

        Args:
            path: File or directory to check (relative to workspace).
        """
        try:
            result = subprocess.run(
                ["python3", "-m", "ruff", "check", path],
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = result.stdout + result.stderr
            if result.returncode == 0:
                return "ruff: All checks passed."
            return f"ruff errors:\n{output[-2000:]}"
        except FileNotFoundError:
            return "ruff not installed."
        except Exception as e:
            return f"ruff failed: {e}"

    return toolset
