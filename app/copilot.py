"""NEXUS Copilot: AG-UI agent for CopilotKit frontend integration.

Exposes the NEXUS agent platform capabilities through the AG-UI protocol,
enabling real-time streaming of agent state to the CopilotKit frontend.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.ag_ui import AGUIApp, StateDeps

from app.agents.builder import design_agent
from app.agents.deep.configs import DEEP_AGENTS
from app.agents.definitions import AGENTS as CODE_AGENTS
from app.agents.factory import run_deep_agent
from app.events import emit_event
from app.mcp import call_mcp_tool, list_mcp_tools, list_registered_servers
from app.memory import add_memory, search_memory
from app.registry import (
    agent_config_from_record,
    get_agent,
    list_agents,
)
from app.tools.registry import get_tools_with_status
from app.traces import save_run
from app.workflows import list_workflows, run_workflow, save_workflow

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


class AgentActivity(BaseModel):
    """A single event in the agent activity feed."""

    timestamp: str = ""
    agent_name: str = ""
    event_type: str = "info"  # start, tool_call, complete, error
    detail: str = ""
    tokens: int = 0
    latency_ms: int = 0


class NexusState(BaseModel):
    """Shared state between the NEXUS copilot agent and the CopilotKit frontend.

    This state is streamed in real-time via AG-UI protocol, allowing the
    frontend to render Generative UI components (AgentCard, CerebroPipelineView,
    MemoryList, ActivityFeed) based on the current state.
    """

    current_agent: AgentInfo = AgentInfo()
    cerebro_stages: list[CerebroStage] = []
    memories: list[MemoryEntry] = []
    activity_log: list[AgentActivity] = []
    active_panel: str = "chat"
    last_agent_config: dict[str, Any] = {}


# ── Activity log helper ──────────────────────────────────────────────

_MAX_ACTIVITY_LOG = 50  # Keep last N events in the streamed state


async def _log_activity(
    state: NexusState,
    *,
    agent_name: str,
    event_type: str,
    detail: str = "",
    tokens: int = 0,
    latency_ms: int = 0,
    run_id: str | None = None,
) -> None:
    """Append an event to the activity log and persist it to the database.

    Keeps the in-memory log bounded to _MAX_ACTIVITY_LOG entries so the
    AG-UI state payload stays small.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    entry = AgentActivity(
        timestamp=now,
        agent_name=agent_name,
        event_type=event_type,
        detail=detail,
        tokens=tokens,
        latency_ms=latency_ms,
    )
    state.activity_log.append(entry)
    # Trim to keep only the most recent events
    if len(state.activity_log) > _MAX_ACTIVITY_LOG:
        state.activity_log = state.activity_log[-_MAX_ACTIVITY_LOG:]

    # Persist to DB (best-effort, don't block on failure)
    try:
        await emit_event(
            agent_name=agent_name,
            event_type=event_type,
            detail=detail,
            run_id=run_id,
            tokens=tokens,
            latency_ms=latency_ms,
        )
    except Exception:
        pass  # Event persistence is best-effort


# ── Copilot agent ────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are NEXUS, an AI agent platform assistant. You help users design, \
build, and manage AI agents. Respond in the same language the user writes in.

CRITICAL RULE — AGENT CREATION PROCESS:
You must NEVER call build_agent on the first user message. No exceptions.
Before creating any agent, you MUST have a thorough conversation to \
understand exactly what the user needs. Follow this process:

1. DISCOVERY PHASE (mandatory, minimum 4 questions across 1-3 messages):
   Ask at least 4 of these important questions before even considering \
   calling build_agent. Adapt them to the context:
   - What specific TASK should this agent perform? (not just the topic — \
     the exact job: summarize, research, generate, analyze, monitor?)
   - What DATA SOURCES or inputs will it work with? (URLs, APIs, files, \
     user-provided text, databases?)
   - What OUTPUT FORMAT do you need? (bullet points, full report, JSON, \
     structured data, conversational?)
   - Who is the TARGET AUDIENCE? (you personally, a team, end users, \
     another system?)
   - Does it need to REMEMBER context across sessions? (one-shot vs \
     persistent memory)
   - Does it need WEB ACCESS to search or fetch live information?
   - Does it need to break work into STEPS/SUBTASKS? (simple response \
     vs multi-step planning)
   - Are there CONSTRAINTS? (tone, length, language, cost limits, \
     specific domains to avoid?)

2. CONFIRMATION PHASE (mandatory):
   Before calling build_agent, summarize what you understood:
   "Let me confirm: you want an agent that [task], using [sources], \
   outputting [format], with [tools]. Should I create it?"
   Only call build_agent AFTER the user explicitly confirms.

3. CREATION PHASE:
   Call build_agent with a rich, detailed description that includes \
   all gathered requirements. The more context you pass, the better \
   the agent will be configured.

TOOLS:
- build_agent: Create an AI agent (ONLY after discovery + confirmation)
- list_agents: List all saved agents in the registry (use to show what exists)
- run_agent: Execute a saved agent by name or ID with a prompt, returns the result
- create_workflow: Create a sequential pipeline of agents (chain agent A -> B -> C)
- run_workflow: Execute a saved workflow with an initial input
- memory_search: Search stored memories for relevant context
- memory_add: Save information to persistent memory
- list_tools: Show all available tools (registry + MCP servers)
- browse_web: Browse a web page and extract content

WORKFLOWS:
Workflows chain multiple agents in sequence. Each step's output becomes the \
next step's input via the {input} placeholder in the prompt template. \
When a user wants to chain agents or create a pipeline, use create_workflow. \
When they want to run an existing workflow, use run_workflow.

For general questions, respond directly without tools.
After using a tool, give a brief summary of the result.
When a user asks to run an agent, use list_agents first if you don't know \
the agent name/ID, then use run_agent to execute it.
"""

copilot_agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    deps_type=StateDeps[NexusState],
    system_prompt=_SYSTEM_PROMPT,
    model_settings={"max_tokens": 1024},
    retries=1,
)


@copilot_agent.tool
async def design_new_agent(ctx: RunContext[StateDeps[NexusState]], description: str) -> str:
    """Design a new AI agent by analyzing requirements and producing Python code.

    Instead of creating a runtime config, this produces code you can review
    and add to app/agents/definitions/. The output is a complete Python file.

    Args:
        description: Detailed description of what the agent should do.
    """
    state: NexusState = ctx.deps.state
    state.active_panel = "agents"

    code = await design_agent(description)

    await _log_activity(
        state,
        agent_name="architect",
        event_type="complete",
        detail="Agent design produced",
    )

    return (
        "Here's the agent definition code. Review it and save to "
        f"app/agents/definitions/:\n\n{code}"
    )


@copilot_agent.tool
async def list_saved_agents(
    ctx: RunContext[StateDeps[NexusState]],
) -> str:
    """List all saved agents in the registry.

    Returns a summary of each agent: name, role, description, and run count.
    Use this to show the user what agents exist before running one.
    """
    state: NexusState = ctx.deps.state
    state.active_panel = "agents"

    lines: list[str] = []

    # Code-defined agents (production)
    if CODE_AGENTS:
        lines.append("**Code-defined agents (production):**")
        for name, cfg in CODE_AGENTS.items():
            lines.append(f"- **{name}** ({cfg.role}) — {cfg.description}")

    # DB-stored agents
    agents = await list_agents(limit=50)
    if agents:
        lines.append("\n**DB-stored agents:**")
        for a in agents:
            runs = a.get("total_runs", 0)
            lines.append(
                f"- **{a['name']}** ({a['role']}) — {a['description']} "
                f"[{runs} runs, id: {a['id'][:8]}...]"
            )

    if not lines:
        return "No agents available."

    return "\n".join(lines)


@copilot_agent.tool
async def run_agent(
    ctx: RunContext[StateDeps[NexusState]],
    agent_name_or_id: str,
    prompt: str,
) -> str:
    """Execute a saved agent by name or ID and return its output.

    Args:
        agent_name_or_id: The agent name or UUID to run.
        prompt: The task or question to send to the agent.
    """
    import time

    state: NexusState = ctx.deps.state

    # Check code-defined agents first (production agents)
    search = agent_name_or_id.lower()
    code_config = CODE_AGENTS.get(agent_name_or_id) or CODE_AGENTS.get(search)
    if code_config is None:
        code_config = next(
            (c for name, c in CODE_AGENTS.items() if name.lower() == search),
            None,
        )

    if code_config is not None:
        config = code_config
        agent_id = f"code:{config.name}"
    else:
        # Fall back to DB-stored agents
        record = await get_agent(agent_name_or_id)
        if record is None:
            agents = await list_agents(limit=100)
            record = next(
                (a for a in agents if a["name"].lower() == search),
                None,
            )
        if record is None:
            available_code = ", ".join(CODE_AGENTS.keys())
            return (
                f"Agent '{agent_name_or_id}' not found. "
                f"Code-defined agents: {available_code}. "
                "Use list_agents to see DB agents."
            )
        config = await agent_config_from_record(record)
        agent_id = record["id"]

    state.current_agent = AgentInfo(
        name=config.name,
        role=config.role,
        model=config.role,
        tools=[],
        status="running",
    )

    # Emit start event
    prompt_preview = prompt[:80] + "..." if len(prompt) > 80 else prompt
    await _log_activity(
        state,
        agent_name=config.name,
        event_type="start",
        detail=f'Running with prompt: "{prompt_preview}"',
    )

    t0 = time.monotonic()
    try:
        result = await run_deep_agent(config, prompt)
    except Exception as e:
        latency_err = int((time.monotonic() - t0) * 1000)
        state.current_agent.status = "idle"
        await _log_activity(
            state,
            agent_name=config.name,
            event_type="error",
            detail=str(e)[:200],
            latency_ms=latency_err,
        )
        return f"Agent execution failed: {e}"

    latency = int((time.monotonic() - t0) * 1000)
    usage = result.get("usage", {})
    output = result["output"]
    total_tokens = usage.get("total_tokens", 0)

    # Save the run trace
    run_record = await save_run(
        agent_id=agent_id,
        agent_name=config.name,
        prompt=prompt,
        output=output[:2000],
        model=config.role,
        role=config.role,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        total_tokens=total_tokens,
        latency_ms=latency,
        source="copilot",
    )

    # Emit complete event
    await _log_activity(
        state,
        agent_name=config.name,
        event_type="complete",
        detail=f"Completed in {latency}ms",
        tokens=total_tokens,
        latency_ms=latency,
        run_id=run_record.get("id"),
    )

    state.current_agent.status = "ready"

    # Truncate long outputs for the chat
    display = output if len(output) <= 2000 else output[:2000] + "\n... (truncated)"
    return (
        f"**{config.name}** result ({latency}ms, {total_tokens} tokens):\n\n{display}"
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
    """List all available tools: built-in registry tools and MCP server tools.

    Args:
        server_name: Filter by MCP server (e.g. "playwright") or empty for all.
    """
    state: NexusState = ctx.deps.state
    state.active_panel = "tools"

    parts: list[str] = []

    # Registry tools (grouped by category)
    registry_tools = await get_tools_with_status()
    categories: dict[str, list[dict[str, Any]]] = {}
    for t in registry_tools:
        categories.setdefault(t["category"], []).append(t)

    registry_lines: list[str] = []
    for cat, cat_tools in sorted(categories.items()):
        tool_entries = []
        for t in cat_tools:
            status = "ready" if t["configured"] and t["enabled"] else "needs config"
            tool_entries.append(f"  - {t['name']}: {t['description']} [{status}]")
        registry_lines.append(f"**{cat}**:\n" + "\n".join(tool_entries))

    ready_count = sum(1 for t in registry_tools if t["configured"] and t["enabled"])
    parts.append(
        f"**Tool Registry** ({ready_count}/{len(registry_tools)} ready):\n\n"
        + "\n\n".join(registry_lines)
    )

    # MCP tools
    if server_name:
        mcp_tools: list[dict[str, Any]] = await list_mcp_tools(server_name=server_name)
        if mcp_tools:
            tool_lines = [f"  - {t['name']}: {t['description']}" for t in mcp_tools]
            header = f"**MCP: {server_name}** ({len(mcp_tools)} tools):"
            parts.append(header + "\n" + "\n".join(tool_lines))
        else:
            parts.append(f"**MCP: {server_name}**: unavailable")
    else:
        servers = list_registered_servers()
        for name in servers:
            mcp_tools = await list_mcp_tools(server_name=name)
            if mcp_tools:
                tool_lines = [f"  - {t['name']}: {t['description']}" for t in mcp_tools]
                parts.append(f"**MCP: {name}** ({len(mcp_tools)} tools):\n" + "\n".join(tool_lines))
            else:
                parts.append(f"**MCP: {name}**: unavailable")

    return "\n\n---\n\n".join(parts)


@copilot_agent.tool
async def create_workflow(
    ctx: RunContext[StateDeps[NexusState]],
    name: str,
    description: str,
    steps: list[dict[str, str]],
) -> str:
    """Create a sequential workflow that chains multiple agents.

    Args:
        name: Short identifier for the workflow (e.g. "research-summarize").
        description: What the workflow does, in one sentence.
        steps: Ordered list of steps. Each step is a dict with "agent_name"
               (name of a saved agent) and "prompt_template" (prompt with
               {input} placeholder for the previous step's output).
    """
    if not steps:
        return "Error: at least one step is required."

    # Validate step structure
    validated_steps: list[dict[str, str]] = []
    for i, step in enumerate(steps):
        agent_name = step.get("agent_name", "")
        if not agent_name:
            return f"Error: step {i} is missing 'agent_name'."
        template = step.get("prompt_template", "{input}")
        validated_steps.append(
            {"agent_name": agent_name, "prompt_template": template}
        )

    record = await save_workflow(
        name=name,
        description=description,
        steps=validated_steps,
    )
    wf_id = record["id"]
    step_names = [s["agent_name"] for s in validated_steps]
    return (
        f"Workflow '{name}' created (id: {wf_id}). "
        f"Pipeline: {' → '.join(step_names)} ({len(validated_steps)} steps)"
    )


@copilot_agent.tool
async def execute_workflow(
    ctx: RunContext[StateDeps[NexusState]],
    workflow_name_or_id: str,
    input_text: str,
) -> str:
    """Execute a saved workflow with an initial input.

    The workflow runs each agent step sequentially, passing each output
    as the next step's input.

    Args:
        workflow_name_or_id: The workflow name or UUID to run.
        input_text: The starting prompt for the first agent in the pipeline.
    """
    import time

    # Find workflow by ID or name
    workflows = await list_workflows(limit=100)
    record = None
    for w in workflows:
        if w["id"] == workflow_name_or_id or w["name"].lower() == workflow_name_or_id.lower():
            record = w
            break

    if record is None:
        available = ", ".join(w["name"] for w in workflows) if workflows else "none"
        return (
            f"Workflow '{workflow_name_or_id}' not found. "
            f"Available workflows: {available}"
        )

    state: NexusState = ctx.deps.state
    wf_name = record.get("name", workflow_name_or_id)

    # Emit workflow start event
    await _log_activity(
        state,
        agent_name=f"workflow:{wf_name}",
        event_type="start",
        detail=f'Workflow started with input: "{input_text[:80]}"',
    )

    t0 = time.monotonic()
    try:
        result = await run_workflow(record["id"], input_text)
    except Exception as e:
        latency_err = int((time.monotonic() - t0) * 1000)
        await _log_activity(
            state,
            agent_name=f"workflow:{wf_name}",
            event_type="error",
            detail=str(e)[:200],
            latency_ms=latency_err,
        )
        return f"Workflow execution failed: {e}"

    latency = int((time.monotonic() - t0) * 1000)
    total_tokens = sum(s.get("tokens", 0) for s in result["steps"])
    status = result.get("status", "completed")

    if status == "awaiting_approval":
        # Workflow paused for human approval
        pending_step = result.get("pending_step", "?")
        await _log_activity(
            state,
            agent_name=f"workflow:{wf_name}",
            event_type="info",
            detail=f"Paused at step {pending_step} — awaiting approval",
            tokens=total_tokens,
            latency_ms=latency,
        )
        final = result["final_output"]
        if len(final) > 2000:
            final = final[:2000] + "\n... (truncated)"
        return (
            f"**{result['workflow_name']}** paused at step {pending_step} "
            f"({result['total_steps']} steps completed, {latency}ms, "
            f"{total_tokens} tokens).\n\n"
            f"**Last output:**\n{final}\n\n"
            f"The workflow requires your approval to continue. "
            f"Use the Approve or Reject buttons in the workflow panel."
        )

    # Emit workflow complete event
    await _log_activity(
        state,
        agent_name=f"workflow:{wf_name}",
        event_type="complete",
        detail=f"Completed {result['total_steps']} steps in {latency}ms",
        tokens=total_tokens,
        latency_ms=latency,
    )

    final = result["final_output"]
    if len(final) > 2000:
        final = final[:2000] + "\n... (truncated)"

    return (
        f"**{result['workflow_name']}** completed "
        f"({result['total_steps']} steps, {latency}ms, {total_tokens} tokens):\n\n"
        f"{final}"
    )


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


@copilot_agent.tool
async def run_deep(
    ctx: RunContext[StateDeps[NexusState]],
    agent_name: str,
    task: str,
) -> str:
    """Run a specialized deep agent (coder, reviewer, or researcher).

    Deep agents run in Docker sandboxes with filesystem access, planning,
    web search, and persistent memory.  They are your AI development team.

    Available agents:
      - nexus-coder: Writes production code with tests and type checking.
      - nexus-reviewer: Reviews code for bugs, security, and quality.
      - nexus-researcher: Investigates technologies and saves to brain.

    Args:
        agent_name: One of "nexus-coder", "nexus-reviewer", "nexus-researcher".
        task: What you want the agent to do (detailed description).
    """
    state: NexusState = ctx.deps.state
    config = DEEP_AGENTS.get(agent_name)
    if config is None:
        available = ", ".join(DEEP_AGENTS.keys())
        return f"Unknown agent: {agent_name}. Available: {available}"

    state.active_panel = "agent"
    state.current_agent = AgentInfo(
        name=config.name,
        role=config.description,
        model=config.role,
        tools=["filesystem", "todo", "web", "memory"],
        status="running",
    )
    await _log_activity(
        state,
        agent_name=agent_name,
        event_type="deep_agent_started",
        detail=task[:80],
    )

    try:
        result = await run_deep_agent(config, task)
        output = result["output"]
        usage = result["usage"]
        total_tokens = usage.get("total_tokens", 0)

        state.current_agent.status = "completed"
        await _log_activity(
            state,
            agent_name=agent_name,
            event_type="deep_agent_completed",
            detail=f"completed ({total_tokens} tokens)",
            tokens=total_tokens,
        )

        await save_run(
            agent_name=config.name,
            prompt=task[:2000],
            output=output[:2000],
            model=config.role,
            role=config.role,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            total_tokens=total_tokens,
            latency_ms=0,
            source="deep",
        )

        if len(output) > 4000:
            output = output[:4000] + "\n... (truncated)"
        return output
    except Exception as e:
        state.current_agent.status = "error"
        return f"Deep agent error: {e}"


@copilot_agent.tool
async def search_brain(
    ctx: RunContext[StateDeps[NexusState]],
    query: str,
) -> str:
    """Search the brain.md knowledge base for information.

    The brain is a Git repo of Markdown notes organized by topic:
    projects, knowledge (stacks, business, architecture), decisions,
    and daily work journals.

    Args:
        query: What to search for (searches across all notes).
    """
    # Use httpx to call our own API which has brain search
    # For now, do a simple grep via the brain tools module
    from app.tools.brain import BRAIN_TOOLS

    tool_names = [t.__name__ for t in BRAIN_TOOLS]
    return (
        f"Brain tools available: {', '.join(tool_names)}. "
        f"Use run_deep with nexus-researcher to search and update the brain. "
        f"The researcher agent has filesystem access to read/write brain notes."
    )


# ── AG-UI app instance ───────────────────────────────────────────────

copilot_app = AGUIApp(
    copilot_agent,
    deps=StateDeps(NexusState()),
)
