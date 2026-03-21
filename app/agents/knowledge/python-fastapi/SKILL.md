---
name: python-fastapi
description: Python 3.12 + FastAPI + Pydantic AI + pydantic-deep conventions and patterns
version: 1.0.0
tags:
  - python
  - fastapi
  - pydantic
  - async
---

# Python + FastAPI Stack

## Runtime
- Python 3.12, async everywhere
- FastAPI with Pydantic v2 models
- Pydantic AI for agent framework
- pydantic-deep (vstorm) for deep agent capabilities
- asyncpg for PostgreSQL (not SQLAlchemy)
- gunicorn + UvicornWorker (4 workers)

## Project Structure
```
app/
  main.py           # FastAPI app, endpoints, observability setup
  config.py         # Pydantic Settings (NEXUS_ env prefix)
  models.py         # Model routing (Haiku vs Groq)
  agents/
    factory.py      # create_deep_agent wrapper
    definitions/    # Code-defined AgentConfig objects
    deep/           # Middleware, hooks, skills
    knowledge/      # Per-agent SKILL.md files
  tools/            # FunctionToolsets
  streaming.py      # WebSocket endpoint
  sessions.py       # Session management
```

## Conventions
- Type hints on ALL functions (strict pyright)
- Docstrings on all public functions
- async def for all I/O operations
- Pydantic BaseModel for request/response schemas
- No bare except -- always catch specific exceptions
- Use `from __future__ import annotations` in every file
- ruff for linting, pyright for type checking

## Patterns
```python
# Config via pydantic-settings
class Settings(BaseSettings):
    database_url: str = "postgresql://..."
    model_config = {"env_prefix": "NEXUS_"}

# Async DB with asyncpg (not SQLAlchemy)
pool = await asyncpg.create_pool(dsn=settings.database_url)
async with pool.acquire() as conn:
    row = await conn.fetchrow("SELECT * FROM ...")

# Agent creation
agent = create_deep_agent(
    model=model,
    instructions=instructions,
    include_todo=True,
    include_filesystem=True,
    ...
)
result = await agent.run(prompt, deps=deps)
```

## Dependencies (pyproject.toml)
- pydantic-ai-slim[groq,anthropic,mcp,logfire,ag-ui]
- pydantic-deep[web-tools,sandbox]
- fastapi, uvicorn, gunicorn
- asyncpg, pgvector, psycopg2-binary
- mem0ai, voyageai
- graphiti-core[falkordb]
- langchain-community
- logfire[fastapi]

## Do NOT
- Use SQLAlchemy (we use raw asyncpg)
- Use sync database calls
- Import from private modules (pydantic_ai._internal)
- Hardcode API keys (use env vars via pydantic-settings)
