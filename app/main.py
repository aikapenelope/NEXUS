"""NEXUS API: FastAPI endpoints for the AI agent builder platform."""

from __future__ import annotations

import os
from typing import Any

import logfire
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agents.builder import build_agent_from_description
from app.agents.cerebro import run_cerebro
from app.agents.factory import AgentConfig, run_agent
from app.copilot import copilot_app
from app.mcp import call_mcp_tool, list_mcp_tools
from app.memory import add_memory, get_user_memories, search_memory
from app.registry import (
    agent_config_from_record,
    get_agent,
    list_agents,
    save_agent,
    update_agent_run_stats,
)

# ── Observability ────────────────────────────────────────────────────
# Logfire auto-instruments Pydantic AI (agent runs, tool calls, LLM
# requests) and FastAPI (HTTP requests, latency, errors) in one call.
# Set LOGFIRE_TOKEN env var to send traces to Logfire Cloud (free tier).
# If no token is set, tracing is disabled (no crash, no data sent).
_logfire_token = os.environ.get("LOGFIRE_TOKEN", "")
if _logfire_token:
    logfire.configure(token=_logfire_token)
else:
    logfire.configure(send_to_logfire=False)

app = FastAPI(
    title="NEXUS",
    description="Self-hosted AI agent builder platform",
    version="0.4.0",
)
logfire.instrument_fastapi(app)

# ── CORS ─────────────────────────────────────────────────────────────
# Allow the Next.js frontend (nexus-frontend container or localhost dev)
# to call the API. In production, restrict origins to the actual domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── AG-UI Copilot endpoint ───────────────────────────────────────────
# Mount the AG-UI app at /api/copilot for CopilotKit frontend integration.
app.mount("/api/copilot", copilot_app)


# ── Request / Response models ────────────────────────────────────────


class BuildRequest(BaseModel):
    """Natural language description of the agent to build."""

    description: str = Field(description="What you want the agent to do, in plain language")


class BuildResponse(BaseModel):
    """The generated AgentConfig from the builder agent, auto-saved to registry."""

    config: AgentConfig
    agent_id: str = Field(description="UUID of the saved agent in the registry")


class RunRequest(BaseModel):
    """Run an agent with a given config and prompt."""

    config: AgentConfig
    prompt: str = Field(description="The task or question for the agent")
    user_id: str | None = Field(
        default=None,
        description="Optional user ID for Mem0 semantic memory integration",
    )


class RunResponse(BaseModel):
    """Agent execution result."""

    output: str
    usage: dict[str, int]


class CerebroRequest(BaseModel):
    """Query for the Cerebro multi-agent analysis pipeline."""

    query: str = Field(description="The topic or question to analyze")


class CerebroResponse(BaseModel):
    """Full Cerebro analysis result with intermediate outputs."""

    result: dict[str, Any]
    usage: dict[str, int]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


# ── Memory request / response models ────────────────────────────────


class MemoryMessage(BaseModel):
    """A single message in a conversation."""

    role: str = Field(description="Message role: 'user' or 'assistant'")
    content: str = Field(description="Message content")


class MemoryAddRequest(BaseModel):
    """Add a conversation to semantic memory."""

    messages: list[MemoryMessage] = Field(
        description="Conversation messages to extract memories from"
    )
    user_id: str = Field(description="User identifier for memory scoping")
    agent_id: str | None = Field(default=None, description="Optional agent identifier")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional metadata tags")


class MemoryAddResponse(BaseModel):
    """Result of adding memories."""

    result: dict[str, Any]


class MemorySearchRequest(BaseModel):
    """Search semantic memory."""

    query: str = Field(description="Natural language search query")
    user_id: str = Field(description="User identifier to scope the search")
    agent_id: str | None = Field(default=None, description="Optional agent identifier")
    limit: int = Field(default=5, description="Max results to return")


class MemorySearchResponse(BaseModel):
    """Memory search results."""

    memories: list[dict[str, Any]]


class MemoryListResponse(BaseModel):
    """All memories for a user."""

    memories: list[dict[str, Any]]


# ── Endpoints ────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok", version="0.4.0")


@app.post("/agents/build", response_model=BuildResponse)
async def build_agent_endpoint(request: BuildRequest) -> BuildResponse:
    """Build an agent from a natural language description.

    Uses Claude Haiku to translate the description into a validated
    AgentConfig, then auto-saves it to the registry.
    """
    try:
        config = await build_agent_from_description(request.description)
        record = await save_agent(config)
        return BuildResponse(config=config, agent_id=record["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Builder agent failed: {e}") from e


@app.post("/agents/run", response_model=RunResponse)
async def run_agent_endpoint(request: RunRequest) -> RunResponse:
    """Run an agent with the given config and prompt.

    The agent is instantiated from the config, executed with token/cost
    limits, and the result is returned with usage metadata.
    """
    try:
        result = await run_agent(request.config, request.prompt, user_id=request.user_id)
        return RunResponse(output=result["output"], usage=result["usage"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}") from e


# ── Agent Registry endpoints ─────────────────────────────────────────


class AgentListResponse(BaseModel):
    """List of saved agents from the registry."""

    agents: list[dict[str, Any]]


class AgentDetailResponse(BaseModel):
    """Single agent detail from the registry."""

    agent: dict[str, Any]


class RunSavedAgentRequest(BaseModel):
    """Run a saved agent by its registry ID."""

    prompt: str = Field(description="The task or question for the agent")
    user_id: str | None = Field(
        default=None,
        description="Optional user ID for Mem0 semantic memory integration",
    )


@app.get("/agents", response_model=AgentListResponse)
async def list_agents_endpoint(limit: int = 50) -> AgentListResponse:
    """List all saved agents from the registry."""
    try:
        agents = await list_agents(limit=limit)
        return AgentListResponse(agents=agents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent list failed: {e}") from e


@app.get("/agents/{agent_id}", response_model=AgentDetailResponse)
async def get_agent_endpoint(agent_id: str) -> AgentDetailResponse:
    """Get a single agent by ID from the registry."""
    try:
        record = await get_agent(agent_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentDetailResponse(agent=record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent get failed: {e}") from e


@app.post("/agents/{agent_id}/run", response_model=RunResponse)
async def run_saved_agent_endpoint(
    agent_id: str, request: RunSavedAgentRequest
) -> RunResponse:
    """Run a saved agent from the registry by its ID.

    Loads the AgentConfig from the registry, runs it, and updates
    the run statistics (total_runs, total_tokens, last_run_at).
    """
    try:
        record = await get_agent(agent_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        config = await agent_config_from_record(record)
        result = await run_agent(config, request.prompt, user_id=request.user_id)
        total_tokens = result["usage"].get("total_tokens", 0)
        await update_agent_run_stats(agent_id, tokens_used=total_tokens)
        return RunResponse(output=result["output"], usage=result["usage"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent run failed: {e}") from e


@app.post("/cerebro/analyze", response_model=CerebroResponse)
async def cerebro_analyze(request: CerebroRequest) -> CerebroResponse:
    """Run the Cerebro multi-agent analysis pipeline.

    Executes four stages: Research (Groq) -> Knowledge (Groq) ->
    Analysis (Haiku) -> Synthesis (Haiku). Each stage has independent
    token and cost limits.
    """
    try:
        result = await run_cerebro(request.query)
        return CerebroResponse(result=result["result"], usage=result["usage"])
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cerebro pipeline failed: {e}",
        ) from e


# ── Memory endpoints ─────────────────────────────────────────────────


@app.post("/memory/add", response_model=MemoryAddResponse)
async def memory_add(request: MemoryAddRequest) -> MemoryAddResponse:
    """Add a conversation to semantic memory.

    Mem0 extracts facts from the messages and stores them as vector
    embeddings in pgvector for later retrieval.
    """
    try:
        messages = [m.model_dump() for m in request.messages]
        result = await add_memory(
            messages=messages,
            user_id=request.user_id,
            agent_id=request.agent_id,
            metadata=request.metadata,
        )
        return MemoryAddResponse(result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory add failed: {e}") from e


@app.post("/memory/search", response_model=MemorySearchResponse)
async def memory_search(
    request: MemorySearchRequest,
) -> MemorySearchResponse:
    """Search semantic memory for relevant facts."""
    try:
        memories = await search_memory(
            query=request.query,
            user_id=request.user_id,
            agent_id=request.agent_id,
            limit=request.limit,
        )
        return MemorySearchResponse(memories=memories)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory search failed: {e}") from e


@app.get("/memory/{user_id}", response_model=MemoryListResponse)
async def memory_list(
    user_id: str,
    agent_id: str | None = None,
) -> MemoryListResponse:
    """Get all memories for a user."""
    try:
        memories = await get_user_memories(
            user_id=user_id,
            agent_id=agent_id,
        )
        return MemoryListResponse(memories=memories)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory list failed: {e}") from e


# ── MCP request / response models ────────────────────────────────────


class MCPToolInfo(BaseModel):
    """Metadata about an MCP tool."""

    name: str
    description: str
    input_schema: dict[str, Any]


class MCPToolsResponse(BaseModel):
    """List of available MCP tools."""

    tools: list[MCPToolInfo]


class MCPCallRequest(BaseModel):
    """Call a specific MCP tool."""

    tool_name: str = Field(description="Name of the MCP tool to call")
    arguments: dict[str, Any] | None = Field(
        default=None, description="Arguments to pass to the tool"
    )
    server_url: str | None = Field(
        default=None,
        description="Optional MCP server URL (defaults to n8n)",
    )


class MCPCallResponse(BaseModel):
    """Result of an MCP tool call."""

    result: Any


# ── MCP endpoints ────────────────────────────────────────────────────


@app.get("/mcp/tools", response_model=MCPToolsResponse)
async def mcp_tools(server_url: str | None = None) -> MCPToolsResponse:
    """List all tools available from the MCP server (n8n by default)."""
    try:
        tools = await list_mcp_tools(server_url)
        return MCPToolsResponse(tools=[MCPToolInfo(**t) for t in tools])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MCP tool listing failed: {e}") from e


@app.post("/mcp/call", response_model=MCPCallResponse)
async def mcp_call(request: MCPCallRequest) -> MCPCallResponse:
    """Call a specific tool on the MCP server."""
    try:
        result = await call_mcp_tool(
            tool_name=request.tool_name,
            arguments=request.arguments,
            server_url=request.server_url,
        )
        return MCPCallResponse(result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MCP tool call failed: {e}") from e
