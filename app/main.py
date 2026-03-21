"""NEXUS API: FastAPI endpoints for the AI agent builder platform."""

from __future__ import annotations

import os
import time
from typing import Any

import logfire
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agents.builder import design_agent
from app.agents.cerebro import run_cerebro
from app.agents.factory import AgentConfig, run_deep_agent
from app.conversations import (
    add_message,
    create_conversation,
    delete_conversation,
    get_conversation,
    get_messages,
    list_conversations,
    update_conversation_title,
)
from app.copilot import copilot_app
from app.evals import EVALUATORS, list_evals, run_eval
from app.events import get_event_stats, list_events
from app.mcp import call_mcp_tool, list_mcp_tools, list_registered_servers
from app.memory import add_memory, get_user_memories, search_memory
from app.registry import (
    agent_config_from_record,
    delete_agent,
    get_agent,
    list_agents,
    save_agent,
    update_agent,
    update_agent_run_stats,
)
from app.tools.registry import (
    TOOL_CATEGORIES,
    get_tools_with_status,
    save_tool_config,
)
from app.traces import get_dashboard_stats, get_monitor_data, get_run, list_runs, save_run
from app.workflows import (
    approve_workflow,
    delete_workflow,
    get_workflow,
    list_workflows,
    reject_workflow,
    run_workflow,
    save_workflow,
)

# ── Observability ────────────────────────────────────────────────────
# Two observability layers:
#   1. Logfire: full-stack (FastAPI, DB, Redis, system metrics)
#   2. Phoenix: AI-specific (agent traces, evals, prompt management)
#
# Logfire: Set LOGFIRE_TOKEN env var for Logfire Cloud (free tier).
_logfire_token = os.environ.get("LOGFIRE_TOKEN", "")
if _logfire_token:
    logfire.configure(token=_logfire_token)
else:
    logfire.configure(send_to_logfire=False)

# Phoenix: Send Pydantic AI traces to self-hosted Phoenix instance.
# Phoenix runs as a Docker container on port 6006.
_phoenix_endpoint = os.environ.get(
    "PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix:6006/v1/traces"
)
try:
    from openinference.instrumentation.pydantic_ai import OpenInferenceSpanProcessor
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    _phoenix_provider = TracerProvider()
    # OpenInference processor enriches spans with AI-specific attributes
    _phoenix_provider.add_span_processor(OpenInferenceSpanProcessor())
    # OTLP exporter sends spans to Phoenix
    _phoenix_provider.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter(endpoint=_phoenix_endpoint))
    )
    trace.set_tracer_provider(_phoenix_provider)
except Exception:
    pass  # Phoenix is optional — if packages missing or unreachable, skip silently

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


# ── Rate limiting middleware ─────────────────────────────────────────
# Applies a sliding-window rate limit (30 req/min by default) to
# expensive endpoints (agent runs, builds, cerebro, workflows).
# Health checks and static reads are exempt.

_RATE_LIMITED_PREFIXES = ("/agents/build", "/agents/run", "/cerebro/", "/workflows/")


@app.middleware("http")
async def rate_limit_middleware(request: Any, call_next: Any) -> Any:
    """Check rate limit for expensive endpoints."""
    from starlette.responses import JSONResponse

    path = request.url.path
    # Only rate-limit write/compute-heavy endpoints
    if request.method == "POST" and any(path.startswith(p) for p in _RATE_LIMITED_PREFIXES):
        from app.cache import check_rate_limit

        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining = await check_rate_limit(f"ip:{client_ip}")
        if not allowed:
            return JSONResponse(
                {"detail": "Rate limit exceeded. Try again in a minute."},
                status_code=429,
                headers={"X-RateLimit-Remaining": str(remaining)},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    return await call_next(request)

# ── AG-UI Copilot endpoint ───────────────────────────────────────────
# Mount the AG-UI app at /api/copilot for CopilotKit frontend integration.
app.mount("/api/copilot", copilot_app)


# ── Request / Response models ────────────────────────────────────────


class BuildRequest(BaseModel):
    """Natural language description of the agent to build."""

    description: str = Field(description="What you want the agent to do, in plain language")


class BuildResponse(BaseModel):
    """Python code for an agent definition, produced by the architect agent."""

    code: str = Field(description="Python code for the agent definition file")


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


class ReadinessResponse(BaseModel):
    """Detailed readiness check response."""

    status: str
    version: str
    checks: dict[str, str]


class AgentCreateRequest(BaseModel):
    """Create an agent manually from a full AgentConfig (no LLM builder)."""

    name: str = Field(description="Short identifier for the agent")
    description: str = Field(description="What the agent does")
    instructions: str = Field(default="", description="System prompt / instructions")
    role: str = Field(
        default="worker",
        description="Model routing role: 'builder', 'analysis', or 'worker'",
    )
    include_todo: bool = Field(default=False)
    include_filesystem: bool = Field(default=False)
    include_subagents: bool = Field(default=False)
    include_skills: bool = Field(default=False)
    include_memory: bool = Field(default=False)
    include_web: bool = Field(default=False)
    context_manager: bool = Field(default=False)
    token_limit: int | None = Field(default=None, description="Max tokens per run")
    cost_budget_usd: float | None = Field(default=None, description="Max USD cost per run")


class AgentCreateResponse(BaseModel):
    """Response after manually creating an agent."""

    agent: dict[str, Any]
    agent_id: str = Field(description="UUID of the saved agent in the registry")


class AgentUpdateRequest(BaseModel):
    """Partial update for an agent. Only provided fields are updated."""

    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    role: str | None = None
    include_todo: bool | None = None
    include_filesystem: bool | None = None
    include_subagents: bool | None = None
    include_skills: bool | None = None
    include_memory: bool | None = None
    include_web: bool | None = None
    context_manager: bool | None = None
    token_limit: int | None = None
    cost_budget_usd: float | None = None
    status: str | None = None


class AgentDeleteResponse(BaseModel):
    """Confirmation of agent deletion."""

    deleted: bool
    agent_id: str


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
    """Lightweight liveness check (no external calls)."""
    return HealthResponse(status="ok", version="0.4.0")


@app.get("/health/ready", response_model=ReadinessResponse)
async def health_ready() -> ReadinessResponse:
    """Deep readiness check: verifies DB, Redis, and MCP connectivity."""
    import asyncpg
    import redis.asyncio as aioredis

    from app.config import settings

    checks: dict[str, str] = {}
    all_ok = True

    # PostgreSQL
    try:
        conn = await asyncpg.connect(dsn=settings.database_url, timeout=5)
        await conn.fetchval("SELECT 1")
        await conn.close()
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"
        all_ok = False

    # Redis
    try:
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=5)
        result = r.ping()  # type stubs say bool, runtime is coroutine
        if hasattr(result, "__await__"):
            await result  # type: ignore[misc]
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        all_ok = False

    # MCP: Playwright
    try:
        tools = await list_mcp_tools(server_name="playwright")
        checks["mcp_playwright"] = f"ok ({len(tools)} tools)"
    except Exception as e:
        checks["mcp_playwright"] = f"error: {e}"
        all_ok = False

    status = "ok" if all_ok else "degraded"
    resp = ReadinessResponse(status=status, version="0.4.0", checks=checks)
    if not all_ok:
        raise HTTPException(status_code=503, detail=resp.model_dump())
    return resp


@app.post("/agents/build", response_model=BuildResponse)
async def build_agent_endpoint(request: BuildRequest) -> BuildResponse:
    """Design an agent from a natural language description.

    Uses Claude Haiku to analyze requirements and produce Python code
    for an agent definition file. The code should be reviewed and saved
    to app/agents/definitions/.
    """
    try:
        code = await design_agent(request.description)
        return BuildResponse(code=code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent architect failed: {e}") from e


@app.post("/agents/run", response_model=RunResponse)
async def run_agent_endpoint(request: RunRequest) -> RunResponse:
    """Run an agent with the given config and prompt.

    The agent is instantiated from the config, executed with token/cost
    limits, and the result is returned with usage metadata.
    """
    try:
        t0 = time.monotonic()
        result = await run_deep_agent(request.config, request.prompt, user_id=request.user_id)
        latency = int((time.monotonic() - t0) * 1000)
        usage = result["usage"]
        await save_run(
            agent_name=request.config.name,
            prompt=request.prompt,
            output=result["output"][:2000],
            model=request.config.role,
            role=request.config.role,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency,
            source="run",
        )
        return RunResponse(output=result["output"], usage=usage)
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


@app.post("/agents", response_model=AgentCreateResponse, status_code=201)
async def create_agent_endpoint(request: AgentCreateRequest) -> AgentCreateResponse:
    """Create an agent manually from explicit fields (no LLM builder).

    Converts the request into an AgentConfig and saves it to the registry.
    If an agent with the same name already exists, it is updated (upsert).
    """
    try:
        config = AgentConfig(
            name=request.name,
            description=request.description,
            instructions=request.instructions,
            role=request.role,
            include_todo=request.include_todo,
            include_filesystem=request.include_filesystem,
            include_subagents=request.include_subagents,
            include_skills=request.include_skills,
            include_memory=request.include_memory,
            include_web=request.include_web,
            context_manager=request.context_manager,
            token_limit=request.token_limit,
            cost_budget_usd=request.cost_budget_usd,
        )
        record = await save_agent(config)
        return AgentCreateResponse(agent=record, agent_id=record["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent creation failed: {e}") from e


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


@app.patch("/agents/{agent_id}", response_model=AgentDetailResponse)
async def update_agent_endpoint(
    agent_id: str, request: AgentUpdateRequest
) -> AgentDetailResponse:
    """Update an agent's configuration.

    Only the fields provided in the request body are updated.
    Omitted fields remain unchanged.
    """
    try:
        # Build updates dict from non-None fields
        updates = request.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        record = await update_agent(agent_id, updates)
        if record is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentDetailResponse(agent=record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent update failed: {e}") from e


@app.delete("/agents/{agent_id}", response_model=AgentDeleteResponse)
async def delete_agent_endpoint(agent_id: str) -> AgentDeleteResponse:
    """Delete an agent from the registry."""
    try:
        deleted = await delete_agent(agent_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentDeleteResponse(deleted=True, agent_id=agent_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent delete failed: {e}") from e


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
        t0 = time.monotonic()
        result = await run_deep_agent(config, request.prompt, user_id=request.user_id)
        latency = int((time.monotonic() - t0) * 1000)
        usage = result["usage"]
        total_tokens = usage.get("total_tokens", 0)
        await update_agent_run_stats(agent_id, tokens_used=total_tokens)
        await save_run(
            agent_id=agent_id,
            agent_name=config.name,
            prompt=request.prompt,
            output=result["output"][:2000],
            model=config.role,
            role=config.role,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            total_tokens=total_tokens,
            latency_ms=latency,
            source="run",
        )
        return RunResponse(output=result["output"], usage=usage)
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
        t0 = time.monotonic()
        result = await run_cerebro(request.query)
        latency = int((time.monotonic() - t0) * 1000)
        usage = result["usage"]
        await save_run(
            agent_name="cerebro",
            prompt=request.query,
            output=str(result["result"].get("summary", ""))[:2000],
            model="multi-model",
            role="analysis",
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency,
            source="cerebro",
        )
        return CerebroResponse(result=result["result"], usage=usage)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cerebro pipeline failed: {e}",
        ) from e


# ── Run history endpoints ────────────────────────────────────────────


class RunListResponse(BaseModel):
    """List of run traces."""

    runs: list[dict[str, Any]]


class RunDetailResponse(BaseModel):
    """Single run trace detail."""

    run: dict[str, Any]


@app.get("/runs", response_model=RunListResponse)
async def list_runs_endpoint(
    limit: int = 50,
    agent_id: str | None = None,
    source: str | None = None,
) -> RunListResponse:
    """List run traces, optionally filtered by agent_id or source."""
    try:
        runs = await list_runs(limit=limit, agent_id=agent_id, source=source)
        return RunListResponse(runs=runs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Run list failed: {e}") from e


@app.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run_endpoint(run_id: str) -> RunDetailResponse:
    """Get a single run trace by ID."""
    try:
        record = await get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return RunDetailResponse(run=record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Run get failed: {e}") from e


# ── Dashboard endpoints ──────────────────────────────────────────────


class DashboardStatsResponse(BaseModel):
    """Aggregate metrics for the dashboard overview."""

    stats: dict[str, Any]


@app.get("/dashboard/stats", response_model=DashboardStatsResponse)
async def dashboard_stats() -> DashboardStatsResponse:
    """Get aggregate dashboard metrics: totals, time-series, breakdowns."""
    try:
        stats = await get_dashboard_stats()
        return DashboardStatsResponse(stats=stats)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Dashboard stats failed: {e}"
        ) from e


class MonitorDataResponse(BaseModel):
    """Combined monitoring data for the monitor page."""

    data: dict[str, Any]


@app.get("/dashboard/monitor", response_model=MonitorDataResponse)
async def dashboard_monitor() -> MonitorDataResponse:
    """Get combined monitoring data: agent status, events, latency series, recent runs."""
    try:
        data = await get_monitor_data()
        return MonitorDataResponse(data=data)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Monitor data failed: {e}"
        ) from e


# ── Events endpoints ─────────────────────────────────────────────────


class EventListResponse(BaseModel):
    """List of agent activity events."""

    events: list[dict[str, Any]]


class EventStatsResponse(BaseModel):
    """Aggregate event statistics."""

    stats: dict[str, Any]


@app.get("/events", response_model=EventListResponse)
async def list_events_endpoint(
    limit: int = 50,
    agent_name: str | None = None,
    event_type: str | None = None,
) -> EventListResponse:
    """List recent agent activity events, newest first."""
    try:
        events = await list_events(
            limit=limit, agent_name=agent_name, event_type=event_type
        )
        return EventListResponse(events=events)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Event list failed: {e}"
        ) from e


@app.get("/events/stats", response_model=EventStatsResponse)
async def event_stats_endpoint() -> EventStatsResponse:
    """Get aggregate event statistics for the monitoring dashboard."""
    try:
        stats = await get_event_stats()
        return EventStatsResponse(stats=stats)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Event stats failed: {e}"
        ) from e


# ── Tool Registry endpoints ──────────────────────────────────────────


class ToolListResponse(BaseModel):
    """List of tools with configuration status."""

    tools: list[dict[str, Any]]


class ToolCategoriesResponse(BaseModel):
    """Available tool categories."""

    categories: list[str]


class ToolConfigureRequest(BaseModel):
    """Configure a tool with required settings."""

    tool_id: str = Field(description="Tool identifier from the catalog")
    config: dict[str, Any] = Field(
        description="Configuration key-value pairs (e.g. api_key)"
    )
    enabled: bool = Field(default=True, description="Enable or disable the tool")


class ToolConfigureResponse(BaseModel):
    """Result of configuring a tool."""

    tool_config: dict[str, Any]


@app.get("/tools", response_model=ToolListResponse)
async def list_tools_endpoint(
    category: str | None = None,
) -> ToolListResponse:
    """List all available tools with their configuration status."""
    try:
        tools = await get_tools_with_status()
        if category:
            tools = [t for t in tools if t["category"] == category]
        return ToolListResponse(tools=tools)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Tool list failed: {e}"
        ) from e


@app.get("/tools/categories", response_model=ToolCategoriesResponse)
async def tool_categories_endpoint() -> ToolCategoriesResponse:
    """List available tool categories."""
    return ToolCategoriesResponse(categories=TOOL_CATEGORIES)


@app.post("/tools/configure", response_model=ToolConfigureResponse)
async def configure_tool_endpoint(
    request: ToolConfigureRequest,
) -> ToolConfigureResponse:
    """Configure a tool with API keys or other settings."""
    try:
        result = await save_tool_config(
            tool_id=request.tool_id,
            config=request.config,
            enabled=request.enabled,
        )
        return ToolConfigureResponse(tool_config=result)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Tool configuration failed: {e}"
        ) from e


# ── Eval endpoints ───────────────────────────────────────────────────


class EvalTestCase(BaseModel):
    """A single test case for evaluation."""

    prompt: str = Field(description="Input prompt for the agent")
    expected: str = Field(description="Expected output or substring")


class RunEvalRequest(BaseModel):
    """Request to run an evaluation suite."""

    dataset: list[EvalTestCase] = Field(
        description="List of test cases to evaluate"
    )
    evaluator: str = Field(
        default="contains",
        description="Evaluator to use: exact_match, contains, or llm_judge",
    )


class EvalResponse(BaseModel):
    """Evaluation result."""

    evaluation: dict[str, Any]


class EvalListResponse(BaseModel):
    """List of evaluations."""

    evaluations: list[dict[str, Any]]


class EvaluatorsResponse(BaseModel):
    """Available evaluators."""

    evaluators: dict[str, str]


@app.post("/agents/{agent_id}/eval", response_model=EvalResponse)
async def run_eval_endpoint(
    agent_id: str,
    request: RunEvalRequest,
) -> EvalResponse:
    """Run an evaluation suite against a saved agent."""
    if request.evaluator not in EVALUATORS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown evaluator: {request.evaluator}. Available: {list(EVALUATORS.keys())}",
        )
    try:
        dataset = [{"prompt": tc.prompt, "expected": tc.expected} for tc in request.dataset]
        result = await run_eval(agent_id, dataset, request.evaluator)
        return EvalResponse(evaluation=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Evaluation failed: {e}"
        ) from e


@app.get("/agents/{agent_id}/evals", response_model=EvalListResponse)
async def list_evals_endpoint(
    agent_id: str,
    limit: int = 20,
) -> EvalListResponse:
    """List evaluations for an agent."""
    try:
        evals = await list_evals(agent_id, limit)
        return EvalListResponse(evaluations=evals)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list evals: {e}"
        ) from e


@app.get("/evals/evaluators", response_model=EvaluatorsResponse)
async def list_evaluators_endpoint() -> EvaluatorsResponse:
    """List available evaluator types."""
    return EvaluatorsResponse(evaluators=EVALUATORS)


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
    server_name: str | None = Field(
        default=None,
        description="Registered server name (e.g. 'playwright')",
    )
    server_url: str | None = Field(
        default=None,
        description="Optional MCP server URL override",
    )


class MCPCallResponse(BaseModel):
    """Result of an MCP tool call."""

    result: Any


# ── MCP endpoints ────────────────────────────────────────────────────


class MCPServersResponse(BaseModel):
    """List of registered MCP servers."""

    servers: dict[str, str]


@app.get("/mcp/servers", response_model=MCPServersResponse)
async def mcp_servers() -> MCPServersResponse:
    """List all registered MCP servers and their URLs."""
    return MCPServersResponse(servers=list_registered_servers())


@app.get("/mcp/tools", response_model=MCPToolsResponse)
async def mcp_tools(
    server_name: str | None = None,
    server_url: str | None = None,
) -> MCPToolsResponse:
    """List all tools available from an MCP server.

    Query params:
        server_name: Registered server (e.g. "playwright"). Defaults to playwright.
        server_url: Direct SSE URL override.
    """
    try:
        tools = await list_mcp_tools(server_url=server_url, server_name=server_name)
        return MCPToolsResponse(tools=[MCPToolInfo(**t) for t in tools])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MCP tool listing failed: {e}") from e


@app.post("/mcp/call", response_model=MCPCallResponse)
async def mcp_call(request: MCPCallRequest) -> MCPCallResponse:
    """Call a specific tool on an MCP server."""
    try:
        result = await call_mcp_tool(
            tool_name=request.tool_name,
            arguments=request.arguments,
            server_name=request.server_name,
            server_url=request.server_url,
        )
        return MCPCallResponse(result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MCP tool call failed: {e}") from e


# ── Workflow models ──────────────────────────────────────────────────


class WorkflowStep(BaseModel):
    """A single step in a workflow pipeline."""

    agent_name: str = Field(description="Name or ID of the agent to run")
    prompt_template: str = Field(
        default="{input}",
        description="Prompt template with {input} placeholder for previous output",
    )
    requires_approval: bool = Field(
        default=False,
        description="If true, workflow pauses after this step for human approval",
    )


class WorkflowCreateRequest(BaseModel):
    """Create a new workflow (sequential agent pipeline)."""

    name: str = Field(description="Short identifier for the workflow")
    description: str = Field(default="", description="What the workflow does")
    steps: list[WorkflowStep] = Field(
        description="Ordered list of agent steps to execute"
    )


class WorkflowCreateResponse(BaseModel):
    """Response after creating a workflow."""

    workflow: dict[str, Any]


class WorkflowListResponse(BaseModel):
    """List of saved workflows."""

    workflows: list[dict[str, Any]]


class WorkflowDetailResponse(BaseModel):
    """Single workflow detail."""

    workflow: dict[str, Any]


class WorkflowDeleteResponse(BaseModel):
    """Confirmation of workflow deletion."""

    deleted: bool
    workflow_id: str


class WorkflowRunRequest(BaseModel):
    """Run a workflow with an initial input."""

    input: str = Field(description="Starting prompt for the first agent in the pipeline")


class WorkflowRunResponse(BaseModel):
    """Result of running a workflow pipeline."""

    workflow_id: str
    workflow_name: str
    steps: list[dict[str, Any]]
    final_output: str
    total_steps: int
    status: str = Field(
        default="completed",
        description="completed, awaiting_approval, or rejected",
    )
    pending_step: int | None = Field(
        default=None, description="Next step index awaiting approval"
    )
    rejection_reason: str | None = Field(
        default=None, description="Reason for rejection, if rejected"
    )


# ── Workflow endpoints ───────────────────────────────────────────────


@app.post("/workflows", response_model=WorkflowCreateResponse, status_code=201)
async def create_workflow_endpoint(
    request: WorkflowCreateRequest,
) -> WorkflowCreateResponse:
    """Create a new workflow (sequential agent pipeline)."""
    try:
        steps_data = [s.model_dump() for s in request.steps]
        record = await save_workflow(
            name=request.name,
            description=request.description,
            steps=steps_data,
        )
        return WorkflowCreateResponse(workflow=record)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Workflow creation failed: {e}"
        ) from e


@app.get("/workflows", response_model=WorkflowListResponse)
async def list_workflows_endpoint(limit: int = 50) -> WorkflowListResponse:
    """List all saved workflows."""
    try:
        workflows = await list_workflows(limit=limit)
        return WorkflowListResponse(workflows=workflows)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Workflow list failed: {e}"
        ) from e


@app.get("/workflows/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow_endpoint(workflow_id: str) -> WorkflowDetailResponse:
    """Get a single workflow by ID."""
    try:
        record = await get_workflow(workflow_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return WorkflowDetailResponse(workflow=record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Workflow get failed: {e}"
        ) from e


@app.delete("/workflows/{workflow_id}", response_model=WorkflowDeleteResponse)
async def delete_workflow_endpoint(
    workflow_id: str,
) -> WorkflowDeleteResponse:
    """Delete a workflow."""
    try:
        deleted = await delete_workflow(workflow_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return WorkflowDeleteResponse(deleted=True, workflow_id=workflow_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Workflow delete failed: {e}"
        ) from e


@app.post(
    "/workflows/{workflow_id}/run", response_model=WorkflowRunResponse
)
async def run_workflow_endpoint(
    workflow_id: str, request: WorkflowRunRequest
) -> WorkflowRunResponse:
    """Execute a workflow: run each agent step sequentially.

    The output of each agent becomes the input for the next step.
    """
    try:
        result = await run_workflow(workflow_id, request.input)
        return WorkflowRunResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Workflow execution failed: {e}"
        ) from e


# ── Workflow HITL endpoints ──────────────────────────────────────────


class WorkflowRejectRequest(BaseModel):
    """Optional reason for rejecting a workflow step."""

    reason: str = Field(default="", description="Why the step was rejected")


@app.post("/workflows/{workflow_id}/approve", response_model=WorkflowRunResponse)
async def approve_workflow_endpoint(
    workflow_id: str,
) -> WorkflowRunResponse:
    """Approve a paused workflow and resume execution from the next step."""
    try:
        result = await approve_workflow(workflow_id)
        return WorkflowRunResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Workflow approval failed: {e}"
        ) from e


@app.post("/workflows/{workflow_id}/reject", response_model=WorkflowRunResponse)
async def reject_workflow_endpoint(
    workflow_id: str,
    request: WorkflowRejectRequest | None = None,
) -> WorkflowRunResponse:
    """Reject a paused workflow, cancelling remaining steps."""
    try:
        reason = request.reason if request else ""
        result = await reject_workflow(workflow_id, reason=reason)
        return WorkflowRunResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Workflow rejection failed: {e}"
        ) from e


# ── Conversation models ──────────────────────────────────────────────


class ConversationCreateRequest(BaseModel):
    """Create a new conversation."""

    title: str | None = Field(default=None, description="Optional title")


class ConversationCreateResponse(BaseModel):
    """Response after creating a conversation."""

    conversation: dict[str, Any]


class ConversationListResponse(BaseModel):
    """List of conversations."""

    conversations: list[dict[str, Any]]


class ConversationDetailResponse(BaseModel):
    """Single conversation detail."""

    conversation: dict[str, Any]


class ConversationUpdateRequest(BaseModel):
    """Update a conversation's title."""

    title: str = Field(description="New title for the conversation")


class ConversationDeleteResponse(BaseModel):
    """Confirmation of conversation deletion."""

    deleted: bool
    conversation_id: str


class MessageAddRequest(BaseModel):
    """Add a message to a conversation."""

    role: str = Field(description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(description="Message text")


class MessageAddResponse(BaseModel):
    """Response after adding a message."""

    message: dict[str, Any]


class MessageListResponse(BaseModel):
    """List of messages in a conversation."""

    messages: list[dict[str, Any]]


# ── Conversation endpoints ───────────────────────────────────────────


@app.post("/conversations", response_model=ConversationCreateResponse, status_code=201)
async def create_conversation_endpoint(
    request: ConversationCreateRequest,
) -> ConversationCreateResponse:
    """Create a new conversation."""
    try:
        record = await create_conversation(title=request.title)
        return ConversationCreateResponse(conversation=record)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Conversation creation failed: {e}"
        ) from e


@app.get("/conversations", response_model=ConversationListResponse)
async def list_conversations_endpoint(
    limit: int = 50,
) -> ConversationListResponse:
    """List conversations ordered by most recently updated."""
    try:
        conversations = await list_conversations(limit=limit)
        return ConversationListResponse(conversations=conversations)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Conversation list failed: {e}"
        ) from e


@app.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation_endpoint(
    conversation_id: str,
) -> ConversationDetailResponse:
    """Get a single conversation by ID."""
    try:
        record = await get_conversation(conversation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationDetailResponse(conversation=record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Conversation get failed: {e}"
        ) from e


@app.patch("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def update_conversation_endpoint(
    conversation_id: str,
    request: ConversationUpdateRequest,
) -> ConversationDetailResponse:
    """Update a conversation's title."""
    try:
        record = await update_conversation_title(conversation_id, request.title)
        if record is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationDetailResponse(conversation=record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Conversation update failed: {e}"
        ) from e


@app.delete("/conversations/{conversation_id}", response_model=ConversationDeleteResponse)
async def delete_conversation_endpoint(
    conversation_id: str,
) -> ConversationDeleteResponse:
    """Delete a conversation and all its messages."""
    try:
        deleted = await delete_conversation(conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationDeleteResponse(deleted=True, conversation_id=conversation_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Conversation delete failed: {e}"
        ) from e


@app.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageAddResponse,
    status_code=201,
)
async def add_message_endpoint(
    conversation_id: str,
    request: MessageAddRequest,
) -> MessageAddResponse:
    """Add a message to a conversation."""
    try:
        # Verify conversation exists
        conv = await get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        record = await add_message(
            conversation_id=conversation_id,
            role=request.role,
            content=request.content,
        )
        return MessageAddResponse(message=record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Message add failed: {e}"
        ) from e


@app.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
async def get_messages_endpoint(
    conversation_id: str,
    limit: int = 200,
) -> MessageListResponse:
    """Get messages for a conversation in chronological order."""
    try:
        # Verify conversation exists
        conv = await get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        messages = await get_messages(conversation_id, limit=limit)
        return MessageListResponse(messages=messages)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Message list failed: {e}"
        ) from e
