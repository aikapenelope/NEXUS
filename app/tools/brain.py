"""Brain tools: read/write the brain.md knowledge base from deep agents.

The brain is a Git repo of plain Markdown files (personal knowledge base).
Deep agents use these tools to persist and retrieve knowledge across sessions.

These tools work with the agent's backend (StateBackend or DockerSandbox)
using the standard file operations: read, write, grep_raw, ls_info.

Note: Git operations (clone, pull, commit, push) require the DockerSandbox
backend with shell access.  When using StateBackend, the brain tools operate
on in-memory files only (useful for testing).
"""

from __future__ import annotations

from pydantic_ai import RunContext
from pydantic_deep import DeepAgentDeps

from app.config import settings

BRAIN_DIR = "/workspace/brain"
BRAIN_REPO_URL = settings.brain_repo_url


def search_knowledge(
    ctx: RunContext[DeepAgentDeps],
    query: str,
    directory: str = "",
) -> str:
    """Search the brain for notes matching a query.

    Uses the backend's grep to search across all .md files.
    Optionally scoped to a subdirectory (e.g. "03-knowledge/stacks").

    Args:
        query: Text to search for (case-insensitive).
        directory: Optional subdirectory to scope the search.

    Returns:
        Matching lines with file paths, or "No results found."
    """
    search_path = f"{BRAIN_DIR}/{directory}" if directory else BRAIN_DIR
    try:
        results = ctx.deps.backend.grep_raw(query, path=search_path)
        if isinstance(results, list):
            lines = [
                f"{m['path']}:{m['line_number']}:{m['line']}" for m in results
            ]
            output = "\n".join(lines[:40])
        else:
            output = str(results).strip()
        return output if output else "No results found."
    except Exception:
        return "No results found."


def read_note(ctx: RunContext[DeepAgentDeps], path: str) -> str:
    """Read a specific note from the brain.

    Args:
        path: Relative path within the brain repo
              (e.g. "02-projects/nexus.md").

    Returns:
        The full content of the note, or an error message if not found.
    """
    full_path = f"{BRAIN_DIR}/{path}"
    try:
        return ctx.deps.backend.read(full_path)
    except Exception as e:
        return f"Error reading {path}: {e}"


def write_note(
    ctx: RunContext[DeepAgentDeps],
    path: str,
    content: str,
) -> str:
    """Write or update a note in the brain.

    Creates the file in the backend's filesystem.  When running in a
    DockerSandbox, the agent should use its shell tool to git commit
    and push after writing.

    Args:
        path: Relative path (e.g. "03-knowledge/stacks/prefect.md").
        content: Full Markdown content to write.

    Returns:
        Confirmation message.
    """
    full_path = f"{BRAIN_DIR}/{path}"
    try:
        ctx.deps.backend.write(full_path, content)
        return f"Saved: {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


def list_notes(
    ctx: RunContext[DeepAgentDeps],
    directory: str = "",
) -> str:
    """List all notes in a brain directory.

    Args:
        directory: Subdirectory to list (e.g. "03-knowledge/stacks").
                   Empty string lists the root.

    Returns:
        Newline-separated list of .md file paths.
    """
    search_path = f"{BRAIN_DIR}/{directory}" if directory else BRAIN_DIR
    try:
        entries = ctx.deps.backend.ls_info(search_path)
        md_files = [str(e["name"]) for e in entries if str(e["name"]).endswith(".md")]
        return "\n".join(md_files) if md_files else "No notes found."
    except Exception:
        return "No notes found."


# All brain tools as a list for easy registration with agents.
BRAIN_TOOLS = [search_knowledge, read_note, write_note, list_notes]
