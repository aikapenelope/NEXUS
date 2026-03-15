"""NEXUS Copilot: AG-UI agent for CopilotKit frontend integration.

Exposes the NEXUS agent platform capabilities through the AG-UI protocol,
enabling real-time streaming of agent state to the CopilotKit frontend.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.ag_ui import AGUIApp, StateDeps

from app.agents.builder import build_agent_from_description
from app.agents.factory import AgentConfig
from app.mcp import call_mcp_tool, list_mcp_tools, list_registered_servers
from app.memory import add_memory, search_memory
from app.registry import save_agent

# ── Shared state (synced to frontend via AG-UI) ─────────────────────


class AgentInfo(BaseModel):
    """Agent metadata displayed in the frontend."""

    name: str = ""
    role: str = ""
    model: str = ""
    tools: list[str] = []
    status: str = "idle"


class CerebroStage(BaseModel):
    """A single stage in the Cerebro analysis pipeline."""

    name: str
    status: str = "pending"
    output: str = ""


class MemoryEntry(BaseModel):
    """A single memory entry from Mem0."""

    id: str = ""
    memory: str = ""
    score: float = 0.0


class NexusState(BaseModel):
    """Shared state between the NEXUS copilot agent and the CopilotKit frontend.

    This state is streamed in real-time via AG-UI protocol, allowing the
    frontend to render Generative UI components (AgentCard, CerebroPipelineView,
    MemoryList) based on the current state.
    """

    current_agent: AgentInfo = AgentInfo()
    cerebro_stages: list[CerebroStage] = []
    memories: list[MemoryEntry] = []
    active_panel: str = "chat"
    last_agent_config: dict[str, Any] = {}


# ── Copilot agent ────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are NEXUS, an AI agent platform assistant. You help users build \
and manage AI agents. Respond in the same language the user writes in.

BUILDING AGENTS:
When a user asks to build or create an agent:
- If the request is vague (e.g. "build a news agent"), ask 2-3 \
clarifying questions BEFORE calling build_agent. Ask about: specific \
task details, data sources, output format preferences.
- If the request is detailed enough, go ahead and call build_agent.
- After building, summarize what was created and how to use it.

TOOLS:
- build_agent: Build an AI agent (only after gathering requirements)
- memory_search: Search stored memories
- memory_add: Save information to memory
- list_tools: Show available MCP tools
- browse_web: Browse a web page

For general questions, respond directly without tools.
After using a tool, give a brief summary of the result.
"""

copilot_agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    deps_type=StateDeps[NexusState],
    system_prompt=_SYSTEM_PROMPT,
    model_settings={"max_tokens": 512},
    retries=1,
)


@copilot_agent.tool
async def build_agent(ctx: RunContext[StateDeps[NexusState]], description: str) -> str:
    """Build an AI agent from a natural language description.

    Args:
        description: What you want the agent to do, in plain language.
    """
    state: NexusState = ctx.deps.state
    state.current_agent = AgentInfo(
        name="Building...", role=description, model="", tools=[], status="building"
    )
    state.active_panel = "agents"

    config: AgentConfig = await build_agent_from_description(description)

    # Derive enabled tools from feature toggles
    enabled_tools: list[str] = []
    if config.include_todo:
        enabled_tools.append("todo")
    if config.include_filesystem:
        enabled_tools.append("filesystem")
    if config.include_subagents:
        enabled_tools.append("subagents")
    if config.include_skills:
        enabled_tools.append("skills")
    if config.include_memory:
        enabled_tools.append("memory")
    if config.include_web:
        enabled_tools.append("web")

    # Auto-save to registry
    record = await save_agent(config)
    agent_id = record["id"]

    state.current_agent = AgentInfo(
        name=config.name,
        role=config.role,
        model=config.role,
        tools=enabled_tools,
        status="ready",
    )
    state.last_agent_config = config.model_dump()

    tools_str = ", ".join(enabled_tools) or "none"
    return (
        f"Agent '{config.name}' built and saved to registry (id: {agent_id}). "
        f"Role: '{config.role}', tools: {tools_str}"
    )


@copilot_agent.tool
async def memory_search(
    ctx: RunContext[StateDeps[NexusState]], query: str, user_id: str = "copilot-user"
) -> str:
    """Search semantic memory for relevant information.

    Args:
        query: Natural language search query.
        user_id: User ID to scope the search.
    """
    state: NexusState = ctx.deps.state
    state.active_panel = "memory"

    results: list[dict[str, Any]] = await search_memory(
        query=query, user_id=user_id, limit=5
    )
    state.memories = [
        MemoryEntry(
            id=str(m.get("id", "")),
            memory=str(m.get("memory", "")),
            score=float(m.get("score", 0.0)),
        )
        for m in results
    ]

    if not results:
        return "No memories found for that query."

    memory_texts = [f"- {m.get('memory', '')}" for m in results]
    return f"Found {len(results)} memories:\n" + "\n".join(memory_texts)


@copilot_agent.tool
async def memory_add(
    ctx: RunContext[StateDeps[NexusState]], content: str, user_id: str = "copilot-user"
) -> str:
    """Add information to semantic memory.

    Args:
        content: The information to remember.
        user_id: User ID to scope the memory.
    """
    messages = [
        {"role": "user", "content": content},
        {"role": "assistant", "content": f"I'll remember: {content}"},
    ]
    result: dict[str, Any] = await add_memory(messages=messages, user_id=user_id)
    return f"Memory added successfully. Result: {result}"


@copilot_agent.tool
async def list_tools(
    ctx: RunContext[StateDeps[NexusState]], server_name: str = ""
) -> str:
    """List available MCP tools from connected servers.

    Args:
        server_name: Server to query ("n8n", "playwright", or empty for all).
    """
    if server_name:
        tools: list[dict[str, Any]] = await list_mcp_tools(server_name=server_name)
        if not tools:
            return f"No tools available from '{server_name}' (server may be unreachable)."
        tool_lines = [f"- {t['name']}: {t['description']}" for t in tools]
        return f"MCP tools from '{server_name}' ({len(tools)}):\n" + "\n".join(tool_lines)

    # List all servers and their tools
    servers = list_registered_servers()
    parts: list[str] = []
    for name in servers:
        tools = await list_mcp_tools(server_name=name)
        if tools:
            tool_lines = [f"  - {t['name']}: {t['description']}" for t in tools]
            parts.append(f"**{name}** ({len(tools)} tools):\n" + "\n".join(tool_lines))
        else:
            parts.append(f"**{name}**: unavailable or no tools")
    return "Connected MCP servers:\n\n" + "\n\n".join(parts)


@copilot_agent.tool
async def browse_web(
    ctx: RunContext[StateDeps[NexusState]],
    url: str,
) -> str:
    """Browse a web page and get its content as structured text.

    Args:
        url: The URL to navigate to.
    """
    try:
        await call_mcp_tool(
            tool_name="browser_navigate",
            arguments={"url": url},
            server_name="playwright",
        )
        result = await call_mcp_tool(
            tool_name="browser_snapshot",
            arguments={},
            server_name="playwright",
        )
        text = str(result)
        if len(text) > 3000:
            text = text[:3000] + "\n... (truncated)"
        return f"Page content from {url}:\n\n{text}"
    except ConnectionError as e:
        return (
            f"Browser unavailable: {e}. "
            "The Playwright MCP server may not be running."
        )
    except Exception as e:
        return f"Browser error: {e}"


# ── AG-UI app instance ───────────────────────────────────────────────

copilot_app = AGUIApp(
    copilot_agent,
    deps=StateDeps(NexusState()),
)
