---
name: postgres-pgvector
description: PostgreSQL 17 + pgvector patterns for NEXUS data and vector operations
version: 1.0.0
tags:
  - postgres
  - pgvector
  - database
  - async
---

# PostgreSQL + pgvector

## Setup
- PostgreSQL 17 via pgvector/pgvector:pg17 Docker image
- pgvector extension for vector embeddings (Mem0 semantic memory)
- asyncpg for all Python database access (not SQLAlchemy)
- Connection pooling via asyncpg.create_pool (min=1, max=5)

## NEXUS Databases
| Database | Purpose |
|----------|---------|
| nexus | Main app data (agents, runs, costs, conversations, workflows, events, tools, memories) |
| phoenix | Phoenix AI observability |

## Key Tables
```sql
nexus_agents        -- Agent registry (name, role, config, run stats)
nexus_runs          -- Run traces (prompt, output, tokens, latency, cost)
nexus_costs         -- Cost tracking per run (USD, tokens)
nexus_memories      -- Mem0 vector embeddings (pgvector, 512 dims)
nexus_conversations -- Chat sessions
nexus_messages      -- Chat messages per conversation
nexus_workflows     -- Sequential agent pipelines
nexus_evals         -- Agent evaluation results
nexus_agent_events  -- Activity log
nexus_tool_configs  -- Tool configuration store
```

## asyncpg Patterns
```python
# Lazy pool singleton
_pool: asyncpg.Pool | None = None

async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(CREATE_TABLE_SQL)
    return _pool

# Query pattern
pool = await _get_pool()
async with pool.acquire() as conn:
    row = await conn.fetchrow("SELECT * FROM nexus_agents WHERE id = $1", agent_id)

# UUID handling
import uuid
if isinstance(d.get("id"), uuid.UUID):
    d["id"] = str(d["id"])
```

## Credentials
- User: nexus, Password: nexus (dev -- needs real secrets for production)
- Connection: postgresql://nexus:nexus@postgres:5432/nexus (internal Docker network)

## Do NOT
- Use SQLAlchemy (raw asyncpg only)
- Create tables without IF NOT EXISTS
- Forget to convert UUID to str in JSON responses
- Open connections without using the pool
