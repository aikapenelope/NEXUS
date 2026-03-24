---
name: performance-optimization
description: Profiling, caching, database query optimization, async patterns, memory management. Use when optimizing slow code or reducing resource usage.
version: 1.0.0
tags:
  - performance
  - profiling
  - caching
  - async
  - optimization
---

# Performance Optimization

## Profiling First
Never optimize without measuring. Profile first, then fix the bottleneck.

```bash
# Python profiling
python -m cProfile -s cumulative app.py
python -m py-spy record -o profile.svg -- python app.py

# Memory profiling
python -m memray run app.py
python -m memray flamegraph output.bin
```

## Async Patterns (Python)
```python
# GOOD: concurrent I/O
results = await asyncio.gather(
    fetch_user(user_id),
    fetch_orders(user_id),
    fetch_preferences(user_id),
)

# BAD: sequential I/O
user = await fetch_user(user_id)
orders = await fetch_orders(user_id)  # waits for user first
prefs = await fetch_preferences(user_id)  # waits for orders first
```

## Database Optimization
```python
# Connection pooling (asyncpg)
pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)

# Batch queries instead of N+1
# BAD: N+1 query
for user_id in user_ids:
    orders = await conn.fetch("SELECT * FROM orders WHERE user_id = $1", user_id)

# GOOD: single query
orders = await conn.fetch(
    "SELECT * FROM orders WHERE user_id = ANY($1)", user_ids
)

# Indexes for frequent queries
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_runs_created_at ON nexus_runs(created_at DESC);
```

## Caching
```python
# Redis for hot data
await redis.setex(f"user:{user_id}", 300, json.dumps(user_data))  # 5min TTL

# In-memory for computed values
from functools import lru_cache

@lru_cache(maxsize=128)
def compute_expensive(key: str) -> dict:
    ...
```

## Streaming for Large Data
```python
# GOOD: stream large files
async def stream_file(path: str):
    async with aiofiles.open(path) as f:
        async for chunk in f:
            yield chunk

# BAD: load entire file into memory
content = open(path).read()  # OOM on large files
```

## Do NOT
- Optimize without profiling first
- Use sync I/O in async code (blocks the event loop)
- Cache without TTL (stale data)
- Create indexes on every column (slows writes)
- Premature optimization — make it work, then make it fast
