"""MCP toolsets for coding: Git operations and code context (tree-sitter).

Git MCP: commits, branches, diffs, log, blame via @modelcontextprotocol/server-git.
Code Context: tree-sitter AST repo map via code-context-provider-mcp.

Both run as local stdio processes via MCPServerStdio (requires npx in container).
Graceful degradation: returns None if npx is not available.
"""

from __future__ import annotations

import logging
import shutil

from pydantic_ai.toolsets import AbstractToolset

logger = logging.getLogger(__name__)


def _has_npx() -> bool:
    """Check if npx is available in PATH."""
    return shutil.which("npx") is not None


def create_git_mcp_toolset(
    repo_dir: str = "/workspace",
) -> AbstractToolset | None:
    """Create Git MCP toolset for repository operations.

    Provides: git_status, git_diff, git_log, git_commit, git_branch,
    git_checkout, git_show, git_blame, search_code, etc.

    Args:
        repo_dir: Root directory of the git repository.

    Returns:
        MCPServerStdio toolset, or None if npx not available.
    """
    if not _has_npx():
        logger.info("npx not available, Git MCP disabled")
        return None

    try:
        from pydantic_ai.mcp import MCPServerStdio

        server = MCPServerStdio(
            "npx",
            ["-y", "@modelcontextprotocol/server-git", "--repository", repo_dir],
        )
        logger.info(f"Git MCP toolset configured (repo: {repo_dir})")
        return server
    except Exception as e:
        logger.warning(f"Git MCP toolset failed: {e}")
        return None


def create_code_context_toolset() -> AbstractToolset | None:
    """Create code context MCP toolset for repository understanding.

    Uses tree-sitter to parse code into AST, extract function signatures
    and class definitions, build dependency graph with PageRank, and
    fit an optimal repo map into a token budget.

    This is the Aider/Claude Code pattern for understanding an entire
    repo without reading every file.

    Returns:
        MCPServerStdio toolset, or None if npx not available.
    """
    if not _has_npx():
        logger.info("npx not available, code context MCP disabled")
        return None

    try:
        from pydantic_ai.mcp import MCPServerStdio

        server = MCPServerStdio(
            "npx",
            ["-y", "code-context-provider-mcp"],
        )
        logger.info("Code context MCP toolset configured (tree-sitter)")
        return server
    except Exception as e:
        logger.warning(f"Code context MCP toolset failed: {e}")
        return None
