"""Model routing for NEXUS: Haiku for smart tasks, GPT-OSS 20B for workers.

API keys are read from environment variables by the provider SDKs:
  - ANTHROPIC_API_KEY for Claude models
  - GROQ_API_KEY for Groq-hosted models (GPT-OSS 20B)
These are injected via Docker env / ESC environment at deploy time.
"""

from app.config import settings

# Model identifiers used by pydantic-ai's string-based model resolution.
# The provider SDKs read API keys from env vars automatically.
HAIKU_MODEL: str = settings.haiku_model
GROQ_MODEL: str = settings.groq_model


def get_model_for_role(role: str) -> str:
    """Return the appropriate model string based on agent role.

    Roles:
        builder  -- Haiku (needs structured output, complex reasoning)
        analysis -- Haiku (synthesis, judgment)
        worker   -- GPT-OSS 20B on Groq (reliable tool calling, fast, cheap)
    """
    if role in ("builder", "analysis"):
        return HAIKU_MODEL
    return GROQ_MODEL
