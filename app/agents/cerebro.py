"""Cerebro: multi-agent analysis pipeline (anterior.com style).

Pipeline stages:
  1. Research  (Groq)  — gather raw information, web search, extract facts
  2. Knowledge (Groq)  — organize facts, identify patterns, build context
  3. Analysis  (Haiku) — deep reasoning, cross-reference, draw conclusions
  4. Synthesis (Haiku) — produce final structured output with recommendations

Each stage runs as an independent pydantic-ai Agent with its own UsageLimits
and cost budget, preventing any single stage from draining tokens.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from app.config import settings
from app.models import GROQ_MODEL, HAIKU_MODEL

# ── Stage output models ─────────────────────────────────────────────


class ResearchOutput(BaseModel):
    """Raw findings from the research stage."""

    facts: list[str] = Field(description="Key facts discovered")
    sources: list[str] = Field(default_factory=list, description="Source references")
    gaps: list[str] = Field(default_factory=list, description="Information gaps identified")


class KnowledgeOutput(BaseModel):
    """Organized knowledge from the knowledge stage."""

    themes: list[str] = Field(description="Major themes identified")
    patterns: list[str] = Field(default_factory=list, description="Patterns across facts")
    context: str = Field(description="Synthesized context paragraph")


class AnalysisOutput(BaseModel):
    """Deep analysis results."""

    findings: list[str] = Field(description="Key analytical findings")
    risks: list[str] = Field(default_factory=list, description="Risks or concerns identified")
    opportunities: list[str] = Field(default_factory=list, description="Opportunities identified")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")


class CerebroResult(BaseModel):
    """Final synthesis output from the full Cerebro pipeline."""

    summary: str = Field(description="Executive summary of the analysis")
    key_insights: list[str] = Field(description="Top insights")
    recommendations: list[str] = Field(description="Actionable recommendations")
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence score")
    # Intermediate outputs for transparency
    research: ResearchOutput = Field(description="Raw research findings")
    knowledge: KnowledgeOutput = Field(description="Organized knowledge")
    analysis: AnalysisOutput = Field(description="Deep analysis")


# ── Stage agents ─────────────────────────────────────────────────────

_research_agent: Agent[None, ResearchOutput] = Agent(
    model=GROQ_MODEL,
    output_type=ResearchOutput,
    instructions=(
        "You are a research analyst. Given a topic or question, gather all relevant "
        "facts, data points, and references. Be thorough and cite sources when possible. "
        "Identify any gaps in available information."
    ),
    retries=2,
)

_knowledge_agent: Agent[None, KnowledgeOutput] = Agent(
    model=GROQ_MODEL,
    output_type=KnowledgeOutput,
    instructions=(
        "You are a knowledge organizer. Given raw research facts, identify major themes, "
        "patterns, and connections. Produce a coherent context paragraph that synthesizes "
        "the information into a structured narrative."
    ),
    retries=2,
)

_analysis_agent: Agent[None, AnalysisOutput] = Agent(
    model=HAIKU_MODEL,
    output_type=AnalysisOutput,
    instructions=(
        "You are a senior analyst. Given organized knowledge about a topic, perform deep "
        "analysis: identify non-obvious findings, assess risks and opportunities, and "
        "assign a confidence score (0-1) based on evidence quality and completeness."
    ),
    retries=2,
)

_synthesis_agent: Agent[None, CerebroResult] = Agent(
    model=HAIKU_MODEL,
    output_type=CerebroResult,
    instructions=(
        "You are a synthesis expert. Given research findings, organized knowledge, and "
        "deep analysis, produce a final executive report with: a clear summary, top "
        "insights, actionable recommendations, and an overall confidence score. "
        "Include the intermediate outputs verbatim for transparency."
    ),
    retries=2,
)


# ── Pipeline orchestrator ────────────────────────────────────────────


async def run_cerebro(query: str) -> dict[str, Any]:
    """Run the full Cerebro analysis pipeline on a query.

    Executes four stages sequentially, each with its own token/cost limits.
    Returns the final CerebroResult plus usage metadata from all stages.
    """
    step_limit = UsageLimits(total_tokens_limit=settings.cerebro_step_token_limit)
    total_usage: dict[str, int] = {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

    def _accumulate(result_usage: Any) -> None:
        total_usage["requests"] += result_usage.requests
        total_usage["input_tokens"] += result_usage.input_tokens or 0
        total_usage["output_tokens"] += result_usage.output_tokens or 0
        total_usage["total_tokens"] += result_usage.total_tokens or 0

    # Stage 1: Research (Groq — cheap)
    research_result = await _research_agent.run(
        f"Research the following topic thoroughly:\n\n{query}",
        usage_limits=step_limit,
    )
    research = research_result.output
    _accumulate(research_result.usage())

    # Stage 2: Knowledge (Groq — cheap)
    knowledge_prompt = (
        f"Organize these research findings into themes and patterns:\n\n"
        f"Facts: {research.facts}\n"
        f"Sources: {research.sources}\n"
        f"Gaps: {research.gaps}"
    )
    knowledge_result = await _knowledge_agent.run(
        knowledge_prompt,
        usage_limits=step_limit,
    )
    knowledge = knowledge_result.output
    _accumulate(knowledge_result.usage())

    # Stage 3: Analysis (Haiku — smart)
    analysis_prompt = (
        f"Analyze this organized knowledge deeply:\n\n"
        f"Themes: {knowledge.themes}\n"
        f"Patterns: {knowledge.patterns}\n"
        f"Context: {knowledge.context}"
    )
    analysis_result = await _analysis_agent.run(
        analysis_prompt,
        usage_limits=step_limit,
    )
    analysis = analysis_result.output
    _accumulate(analysis_result.usage())

    # Stage 4: Synthesis (Haiku — smart)
    synthesis_prompt = (
        f"Produce a final executive report from these intermediate results:\n\n"
        f"RESEARCH:\n{research.model_dump_json()}\n\n"
        f"KNOWLEDGE:\n{knowledge.model_dump_json()}\n\n"
        f"ANALYSIS:\n{analysis.model_dump_json()}"
    )
    synthesis_result = await _synthesis_agent.run(
        synthesis_prompt,
        usage_limits=step_limit,
    )
    _accumulate(synthesis_result.usage())

    return {
        "result": synthesis_result.output.model_dump(),
        "usage": total_usage,
    }
