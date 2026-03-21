# NEXUS AI Agent Platform

## Stack
- Python 3.12, FastAPI, Pydantic AI, pydantic-deep (vstorm)
- TypeScript, Next.js 15, CopilotKit, React, Tailwind CSS
- PostgreSQL 17 + pgvector, Redis 7, FalkorDB (Graphiti)
- Docker, Docker Compose, Hetzner Cloud, Pulumi (TypeScript)
- Observability: Phoenix (OpenTelemetry), Logfire

## Project Structure
```
app/
  agents/
    factory.py          # Agent builder (create_deep_agent wrapper)
    builder.py          # Agent architect (generates code, not runtime configs)
    cerebro.py          # Multi-model analysis pipeline
    definitions/        # Code-defined agents (CODING_AGENTS + GENERAL_AGENTS)
    deep/               # Middleware, hooks, skills (vstorm-compatible)
    knowledge/          # Per-agent SKILL.md files
  tools/                # FunctionToolsets (brain, remember, graphiti, langchain)
  config.py             # Pydantic Settings (NEXUS_ prefix)
  main.py               # FastAPI app + observability setup
  copilot.py            # AG-UI copilot for CopilotKit frontend
  memory.py             # Mem0 semantic memory (pgvector + Voyage AI)
  mcp.py                # Playwright MCP client
  registry.py           # Agent CRUD (asyncpg)
  traces.py             # Run history + cost tracking
frontend/               # Next.js dashboard + chat UI
docker-compose.yml      # 9 services
```

## Conventions
- Type hints on every function (strict pyright compliance)
- Docstrings on every public function and class
- Use ruff for linting, pyright for type checking
- No bare except clauses -- always catch specific exceptions
- No hardcoded secrets -- use env vars via pydantic-settings
- Async everywhere -- all DB and API calls are async
- snake_case for Python, camelCase for TypeScript

## Agent Architecture
- All agents use `create_deep_agent()` from pydantic-deep
- `BASE_PROMPT` is prepended to all agent instructions
- Every agent gets: hooks, middleware (audit + permissions + loop detection),
  sliding window, eviction, cost tracking, checkpointing, context discovery
- Coding agents use `DockerSandbox` backend, others use `StateBackend`
- Skills loaded from: per-agent knowledge/ > shared deep/skills/ > bundled_skills

## Before Committing
- `pyright app/` must report 0 errors
- `ruff check app/` must pass
- Run existing tests if present

## Do NOT
- Modify docker-compose.yml without understanding resource limits
- Change model routing in models.py without cost analysis
- Add dependencies without checking pyproject.toml compatibility
- Touch frontend/ without rebuilding the Docker image
- Hardcode API keys, passwords, or connection strings
