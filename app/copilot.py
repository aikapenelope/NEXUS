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
from app.mcp import list_mcp_tools
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
        "5. List available MCP tools\n\n"
        "Be concise and helpful. When building agents, confirm the config "
        "before running. When running Cerebro, explain each stage."
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
async def list_mcp_tools_tool(ctx: RunContext[StateDeps[NexusState]]) -> str:
    """List all available MCP tools from the n8n server."""
    tools: list[dict[str, Any]] = await list_mcp_tools()
    if not tools:
        return "No MCP tools available (n8n server may be unreachable)."

    tool_lines = [f"- {t['name']}: {t['description']}" for t in tools]
    return f"Available MCP tools ({len(tools)}):\n" + "\n".join(tool_lines)


# ── AG-UI app instance ───────────────────────────────────────────────

copilot_app = AGUIApp(copilot_agent, deps=StateDeps(NexusState()))
