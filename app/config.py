"""NEXUS platform configuration via environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the NEXUS platform.

    All values are read from environment variables (or a .env file).
    Secrets come from the ESC environment nexus/secrets at deploy time.
    """

    # ── LLM API keys ────────────────────────────────────────────────
    anthropic_api_key: str = Field(description="Anthropic API key for Claude Haiku")
    groq_api_key: str = Field(description="Groq API key for Llama workers")

    # ── Model routing ───────────────────────────────────────────────
    # Builder / analysis tasks use Haiku (smarter, paid)
    haiku_model: str = "anthropic:claude-haiku-4-5-20251001"
    # Worker / cheap tasks use Groq (fast, free tier)
    groq_model: str = "groq:llama-3.3-70b-versatile"

    # ── Token limits (per agent run) ────────────────────────────────
    builder_token_limit: int = 16_000
    worker_token_limit: int = 8_000
    cerebro_step_token_limit: int = 12_000

    # ── Cost budgets (USD per agent run) ────────────────────────────
    builder_cost_budget: float = 0.10
    worker_cost_budget: float = 0.02
    cerebro_cost_budget: float = 0.25

    # ── PostgreSQL (pgvector) ───────────────────────────────────────
    database_url: str = "postgresql://nexus:nexus@localhost:5432/nexus"

    # ── Redis ───────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── MCP (n8n workflow automation) ─────────────────────────────────
    # Default SSE URL for n8n's MCP Server Trigger node.
    # Override per-workflow via the API if needed.
    n8n_mcp_url: str = "http://n8n:5678/mcp"

    # ── Server ──────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    model_config = {"env_prefix": "NEXUS_", "env_file": ".env", "env_file_encoding": "utf-8"}


# Singleton instance — import this everywhere
settings = Settings()  # type: ignore[call-arg]
