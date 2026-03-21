"""Brain toolset: FunctionToolset wrapper for knowledge base access.

Wraps the brain tools (search, read, write, list notes) as a proper
FunctionToolset that can be registered with create_deep_agent via the
toolsets parameter. This gives agents direct access to the brain.md
knowledge base without going through API endpoints.

The brain is a Git repo of plain Markdown files (personal knowledge base).
Tools work with the agent's backend (StateBackend or DockerSandbox).
"""

from __future__ import annotations

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset
from pydantic_deep import DeepAgentDeps

from app.config import settings

BRAIN_DIR = "/workspace/brain"
BRAIN_REPO_URL = settings.brain_repo_url


def create_brain_toolset(
    toolset_id: str = "brain",
) -> FunctionToolset[DeepAgentDeps]:
    """Create a FunctionToolset with brain knowledge base tools.

    Args:
        toolset_id: Unique identifier for the toolset.

    Returns:
        FunctionToolset with search_knowledge, read_note, write_note, list_notes.
    """
    toolset: FunctionToolset[DeepAgentDeps] = FunctionToolset(id=toolset_id)

    @toolset.tool
    async def search_knowledge(
        ctx: RunContext[DeepAgentDeps],
        query: str,
        directory: str = "",
    ) -> str:
        """Search the brain knowledge base for notes matching a query.

        Uses grep to search across all .md files in the brain repo.
        Optionally scoped to a subdirectory.

        Args:
            query: Text to search for (case-insensitive).
            directory: Optional subdirectory to scope the search
                       (e.g. "03-knowledge/stacks").
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

    @toolset.tool
    async def read_note(
        ctx: RunContext[DeepAgentDeps],
        path: str,
    ) -> str:
        """Read a specific note from the brain knowledge base.

        Args:
            path: Relative path within the brain repo
                  (e.g. "02-projects/nexus.md").
        """
        full_path = f"{BRAIN_DIR}/{path}"
        try:
            return ctx.deps.backend.read(full_path)
        except Exception as e:
            return f"Error reading {path}: {e}"

    @toolset.tool
    async def write_note(
        ctx: RunContext[DeepAgentDeps],
        path: str,
        content: str,
    ) -> str:
        """Write or update a note in the brain knowledge base.

        Creates the file in the backend's filesystem. When running in a
        DockerSandbox, use the execute tool to git commit and push after writing.

        Args:
            path: Relative path (e.g. "03-knowledge/stacks/prefect.md").
            content: Full Markdown content to write.
        """
        full_path = f"{BRAIN_DIR}/{path}"
        try:
            ctx.deps.backend.write(full_path, content)
            return f"Saved: {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"

    @toolset.tool
    async def list_notes(
        ctx: RunContext[DeepAgentDeps],
        directory: str = "",
    ) -> str:
        """List all notes in a brain knowledge base directory.

        Args:
            directory: Subdirectory to list (e.g. "03-knowledge/stacks").
                       Empty string lists the root.
        """
        search_path = f"{BRAIN_DIR}/{directory}" if directory else BRAIN_DIR
        try:
            entries = ctx.deps.backend.ls_info(search_path)
            md_files = [str(e["name"]) for e in entries if str(e["name"]).endswith(".md")]
            return "\n".join(md_files) if md_files else "No notes found."
        except Exception:
            return "No notes found."

    return toolset
