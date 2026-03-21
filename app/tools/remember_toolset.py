"""Remember toolset: explicit memory persistence for agents.

Following the DeepResearch pattern, this gives agents a simple `remember`
tool that writes facts to /workspace/MEMORY.md. More intuitive than the
built-in write_memory tool because it has a single-purpose interface.

The agent calls `remember("User prefers Spanish")` and the fact is
appended to MEMORY.md, which is also injected as a context file so
the agent sees it at the start of every run.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset
from pydantic_deep import DeepAgentDeps


def create_remember_toolset(
    toolset_id: str = "remember-tool",
) -> FunctionToolset[DeepAgentDeps]:
    """Create a FunctionToolset with a single `remember` tool.

    Args:
        toolset_id: Unique identifier for the toolset.

    Returns:
        FunctionToolset with the remember tool.
    """
    toolset: FunctionToolset[DeepAgentDeps] = FunctionToolset(id=toolset_id)

    @toolset.tool
    async def remember(ctx: RunContext[DeepAgentDeps], fact: str) -> str:
        """Save a fact to persistent memory.

        Call this IMMEDIATELY when the user shares ANY personal information
        (name, preferences, project details, etc.) or asks you to remember
        something. Your memory resets every session -- this tool is the ONLY
        way to persist information across sessions.

        Examples of when to call this:
        - User says "my name is Ana" -> remember("User's name is Ana")
        - User says "I work at Acme" -> remember("User works at Acme Corp")
        - User says "use Spanish" -> remember("User prefers Spanish language")
        - User says "remember X" -> remember("X")

        Args:
            fact: The fact to save (short, clear statement).

        Returns:
            Confirmation message.
        """
        backend = ctx.deps.backend
        memory_path = "/workspace/MEMORY.md"
        try:
            data: Any = backend.read(memory_path)
            content = data.decode("utf-8") if isinstance(data, bytes) else str(data)
        except Exception:
            content = ""

        if not content.strip():
            content = "# Agent Memory\n\n"

        content = content.rstrip("\n") + "\n- " + fact + "\n"

        if isinstance(content, str):
            backend.write(memory_path, content)
        else:
            backend.write(memory_path, content.encode("utf-8"))

        return f"Saved to memory: {fact}"

    return toolset
