"""POST /tasks/code endpoint: the Devin-style coding task runner.

Accepts a repo URL + task description, creates a session with LocalBackend,
clones the repo into the session workspace, runs the coding agent, and
returns the diff. Optionally opens a PR via GitHub MCP.

This is the core endpoint that makes NEXUS a coding machine.
"""

from __future__ import annotations

import logging
import subprocess
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.definitions import CODING_AGENTS
from app.agents.factory import AgentConfig, build_agent
from app.sessions import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


class CodeTaskRequest(BaseModel):
    """Request body for POST /tasks/code."""

    repo_url: str = Field(..., description="Git repository URL to clone")
    task: str = Field(..., description="Task description for the coding agent")
    branch: str = Field("main", description="Branch to work from")
    agent: str = Field("nexus-developer", description="Agent to use")
    token_limit: int = Field(50000, description="Max tokens for the run")
    cost_budget_usd: float = Field(1.0, description="Max cost in USD")


class CodeTaskResponse(BaseModel):
    """Response from POST /tasks/code."""

    session_id: str
    status: str
    output: str
    diff: str
    files_changed: list[str]
    tokens_used: int


def _clone_repo(repo_url: str, target_dir: Path, branch: str) -> None:
    """Clone a git repo into the target directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(target_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr}")


def _get_diff(workspace: Path) -> tuple[str, list[str]]:
    """Get git diff (tracked + untracked) and list of changed files."""
    # Stage all changes including new files
    subprocess.run(["git", "add", "-A"], cwd=str(workspace), capture_output=True)

    # Get diff of staged changes
    result = subprocess.run(
        ["git", "diff", "--cached", "--stat"],
        capture_output=True,
        text=True,
        cwd=str(workspace),
    )
    files = [
        line.split("|")[0].strip()
        for line in result.stdout.strip().split("\n")
        if "|" in line
    ]

    diff_result = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True,
        text=True,
        cwd=str(workspace),
    )

    # Reset staging (don't leave dirty index)
    subprocess.run(["git", "reset", "HEAD"], cwd=str(workspace), capture_output=True)

    return diff_result.stdout, files


@router.post("/code", response_model=CodeTaskResponse)
async def run_code_task(request: CodeTaskRequest) -> CodeTaskResponse:
    """Run a coding task on a git repository.

    1. Creates a session with persistent LocalBackend
    2. Clones the repo into the session workspace
    3. Runs the coding agent with the task
    4. Returns the diff of changes made

    This is the Devin-style endpoint: give it a repo + task,
    get back code changes.
    """
    session_id = f"task-{uuid.uuid4().hex[:8]}"

    # Get agent config
    config = CODING_AGENTS.get(request.agent)
    if config is None:
        config = AgentConfig(
            name=request.agent,
            description="coding agent",
            instructions="You are a coding assistant.",
            role="analysis",
            include_todo=True,
            include_filesystem=True,
            use_sandbox=False,
            token_limit=request.token_limit,
            cost_budget_usd=request.cost_budget_usd,
        )

    # Override limits and use light_mode for efficiency
    overrides = {
        **config.__dict__,
        "token_limit": request.token_limit,
        "cost_budget_usd": request.cost_budget_usd,
        "use_sandbox": False,
        "light_mode": True,
    }
    config = AgentConfig(**overrides)

    # Create persistent session
    session = session_manager.create(session_id, config)
    workspace = session.session_dir / "workspace"

    # Clone repo
    try:
        _clone_repo(request.repo_url, workspace, request.branch)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to clone repo: {e}") from e

    # Build and run agent with Git MCP for repo operations
    try:
        from app.tools.coding_mcps import create_code_context_toolset, create_git_mcp_toolset
        from app.tools.playwright_toolset import create_playwright_toolset

        agent = build_agent(config)

        # Add Git MCP + code-context + Playwright toolsets
        extra_toolsets = []
        git_mcp = create_git_mcp_toolset(repo_dir=str(workspace))
        if git_mcp is not None:
            extra_toolsets.append(git_mcp)
        code_ctx = create_code_context_toolset()
        if code_ctx is not None:
            extra_toolsets.append(code_ctx)
        playwright = create_playwright_toolset()
        if playwright is not None:
            extra_toolsets.append(playwright)

        from pydantic_ai.usage import UsageLimits

        usage_limits = UsageLimits(
            total_tokens_limit=request.token_limit,
            request_limit=50,
        )

        # Inject repo context into the task prompt
        prompt = (
            f"You are working in a git repository cloned at {workspace}. "
            f"The repo was cloned from {request.repo_url} (branch: {request.branch}).\n\n"
            f"Task: {request.task}\n\n"
            f"After completing the task, make sure all changes are saved to files. "
            f"If you edit Python files, run check_types to verify no type errors."
        )

        # Run with retry on token limit exceeded
        output = "Task completed."
        total_tokens = 0
        last_error = None

        for attempt in range(2):
            try:
                retry_prompt = prompt if attempt == 0 else (
                    f"{prompt}\n\n(Retry: be more concise, fewer tool calls.)"
                )
                result = await agent.run(
                    retry_prompt,
                    deps=session.deps,
                    usage_limits=usage_limits,
                )
                output = str(result.output) if result.output else "Task completed."
                total_tokens = result.usage().total_tokens if result.usage() else 0
                last_error = None
                break
            except Exception as retry_err:
                last_error = retry_err
                logger.warning(f"Task attempt {attempt + 1} failed: {retry_err}")

        if last_error is not None:
            raise last_error

    except Exception as e:
        logger.exception("Code task failed")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}") from e

    # Get diff
    try:
        diff, files_changed = _get_diff(workspace)
    except Exception:
        diff = ""
        files_changed = []

    return CodeTaskResponse(
        session_id=session_id,
        status="completed",
        output=output,
        diff=diff,
        files_changed=files_changed,
        tokens_used=total_tokens,
    )
