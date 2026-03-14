"""NEXUS API: FastAPI endpoints for the AI agent builder platform."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agents.builder import build_agent_from_description
from app.agents.cerebro import run_cerebro
from app.agents.factory import AgentConfig, run_agent

app = FastAPI(
    title="NEXUS",
    description="Self-hosted AI agent builder platform",
    version="0.1.0",
)


# ── Request / Response models ────────────────────────────────────────


class BuildRequest(BaseModel):
    """Natural language description of the agent to build."""

    description: str = Field(description="What you want the agent to do, in plain language")


class BuildResponse(BaseModel):
    """The generated AgentConfig from the builder agent."""

    config: AgentConfig


class RunRequest(BaseModel):
    """Run an agent with a given config and prompt."""

    config: AgentConfig
    prompt: str = Field(description="The task or question for the agent")


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


# ── Endpoints ────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/agents/build", response_model=BuildResponse)
async def build_agent_endpoint(request: BuildRequest) -> BuildResponse:
    """Build an agent from a natural language description.

    Uses Claude Haiku to translate the description into a validated AgentConfig.
    """
    try:
        config = await build_agent_from_description(request.description)
        return BuildResponse(config=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Builder agent failed: {e}") from e


@app.post("/agents/run", response_model=RunResponse)
async def run_agent_endpoint(request: RunRequest) -> RunResponse:
    """Run an agent with the given config and prompt.

    The agent is instantiated from the config, executed with token/cost limits,
    and the result is returned with usage metadata.
    """
    try:
        result = await run_agent(request.config, request.prompt)
        return RunResponse(output=result["output"], usage=result["usage"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}") from e


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
        raise HTTPException(status_code=500, detail=f"Cerebro pipeline failed: {e}") from e
