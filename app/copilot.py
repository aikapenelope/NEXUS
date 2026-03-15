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
from app.agents.cerebro import run_cerebro
from app.agents.factory import AgentConfig, run_agent
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

copilot_agent = Agent(
    "groq:llama-3.3-70b-versatile",
    deps_type=StateDeps[NexusState],
    system_prompt=(
        "You are NEXUS, an AI agent platform assistant. You help users build, "
        "run, and manage AI agents. You can:\n"
        "1. Build agents from natural language descriptions\n"
        "2. Run agents with specific tasks\n"
        "3. Run Cerebro multi-agent analysis pipelines\n"
        "4. Search and manage semantic memory\n"
        "5. List available MCP tools from connected servers\n"
        "6. Browse the web using a headless browser (navigate, click, extract)\n\n"
        "Be concise and helpful. When building agents, confirm the config "
        "before running. When running Cerebro, explain each stage. "
        "When browsing the web, use the browse_web tool to navigate to URLs "
        "and extract content from pages."
    ),
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
async def run_agent_tool(
    ctx: RunContext[StateDeps[NexusState]], prompt: str, user_id: str = "copilot-user"
) -> str:
    """Run the last built agent with a specific task.

    Args:
        prompt: The task or question for the agent.
        user_id: User ID for memory integration.
    """
    state: NexusState = ctx.deps.state
    if not state.last_agent_config:
        return "No agent has been built yet. Use build_agent first."

    state.current_agent.status = "running"
    config = AgentConfig(**state.last_agent_config)
    result: dict[str, Any] = await run_agent(config, prompt, user_id=user_id)
    state.current_agent.status = "completed"

    return f"Agent output: {result['output']}\n\nTokens used: {result['usage']}"


@copilot_agent.tool
async def run_cerebro_tool(ctx: RunContext[StateDeps[NexusState]], query: str) -> str:
    """Run the Cerebro multi-agent analysis pipeline on a topic.

    Args:
        query: The topic or question to analyze in depth.
    """
    state: NexusState = ctx.deps.state
    stages = ["Research", "Knowledge", "Analysis", "Synthesis"]
    state.cerebro_stages = [CerebroStage(name=s, status="pending") for s in stages]
    state.active_panel = "cerebro"

    # Mark first stage as running
    state.cerebro_stages[0].status = "running"

    result: dict[str, Any] = await run_cerebro(query)

    # Mark all stages complete with outputs
    cerebro_result: dict[str, Any] = result.get("result", {})
    stage_keys = ["research", "knowledge", "analysis", "synthesis"]
    for i, key in enumerate(stage_keys):
        stage_output = cerebro_result.get(key, "")
        output_text = str(stage_output)[:200] if stage_output else "Completed"
        state.cerebro_stages[i] = CerebroStage(
            name=stages[i], status="completed", output=output_text
        )

    return f"Cerebro analysis complete. Usage: {result.get('usage', {})}"


@copilot_agent.tool
async def memory_search_tool(
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
async def memory_add_tool(
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
async def list_mcp_tools_tool(
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
    action: str = "snapshot",
) -> str:
    """Browse a web page using the headless browser.

    Navigates to the URL and performs the requested action. Uses the
    Playwright MCP server for browser automation.

    Args:
        url: The URL to navigate to.
        action: What to do on the page. Options:
            "snapshot" - Get the page accessibility tree (default, best for reading)
            "screenshot" - Take a screenshot of the page
            "content" - Get the full page HTML content
    """
    try:
        # Navigate to the URL
        await call_mcp_tool(
            tool_name="browser_navigate",
            arguments={"url": url},
            server_name="playwright",
        )

        # Perform the requested action
        if action == "screenshot":
            result = await call_mcp_tool(
                tool_name="browser_screenshot",
                arguments={},
                server_name="playwright",
            )
            return f"Screenshot taken of {url}. Result: {str(result)[:500]}"

        # Default: get accessibility snapshot (structured text)
        result = await call_mcp_tool(
            tool_name="browser_snapshot",
            arguments={},
            server_name="playwright",
        )
        # Truncate to avoid overwhelming the LLM context
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


@copilot_agent.tool
async def browser_action(
    ctx: RunContext[StateDeps[NexusState]],
    tool_name: str,
    arguments: str = "{}",
) -> str:
    """Call any Playwright browser tool directly.

    For advanced browser interactions beyond navigate/snapshot. Use
    list_mcp_tools_tool with server_name="playwright" to see all
    available tools.

    Args:
        tool_name: The Playwright MCP tool name (e.g., "browser_click").
        arguments: JSON string of arguments for the tool.
    """
    import json

    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return f"Invalid JSON arguments: {arguments}"

    try:
        result = await call_mcp_tool(
            tool_name=tool_name,
            arguments=args,
            server_name="playwright",
        )
        text = str(result)
        if len(text) > 3000:
            text = text[:3000] + "\n... (truncated)"
        return f"Browser tool '{tool_name}' result:\n{text}"
    except ConnectionError as e:
        return f"Browser unavailable: {e}"
    except Exception as e:
        return f"Browser tool error: {e}"


# ── AG-UI app instance ───────────────────────────────────────────────

copilot_app = AGUIApp(copilot_agent, deps=StateDeps(NexusState()))
