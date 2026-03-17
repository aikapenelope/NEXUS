"""Redis cache and rate limiting for the NEXUS platform.

Provides:
- Agent result caching: cache run_deep_agent results by hash(agent_name+prompt)
  with configurable TTL to avoid re-running identical queries.
- Rate limiting: sliding-window rate limiter by key (e.g. IP address) to
  prevent abuse of expensive LLM endpoints.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# ── Redis connection (lazy singleton) ────────────────────────────────

_redis: aioredis.Redis | None = None  # type: ignore[type-arg]


async def _get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    """Return the shared async Redis connection."""
    global _redis  # noqa: PLW0603
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
        )
    return _redis


# ── Agent result cache ───────────────────────────────────────────────

_CACHE_PREFIX = "nexus:cache:"
_DEFAULT_TTL = 300  # 5 minutes


def _cache_key(agent_name: str, prompt: str) -> str:
    """Build a deterministic cache key from agent name and prompt."""
    raw = f"{agent_name.lower().strip()}:{prompt.strip()}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{_CACHE_PREFIX}{digest}"


async def get_cached_result(
    agent_name: str, prompt: str
) -> dict[str, Any] | None:
    """Look up a cached agent result.

    Returns the cached dict (with "output" and "usage" keys) or None.
    """
    try:
        r = await _get_redis()
        key = _cache_key(agent_name, prompt)
        data = await r.get(key)
        if data is not None:
            logger.debug("Cache HIT for %s", key)
            return json.loads(data)  # type: ignore[no-any-return]
    except Exception:
        logger.debug("Cache lookup failed, treating as miss", exc_info=True)
    return None


async def set_cached_result(
    agent_name: str,
    prompt: str,
    result: dict[str, Any],
    ttl: int = _DEFAULT_TTL,
) -> None:
    """Store an agent result in the cache with a TTL (seconds)."""
    try:
        r = await _get_redis()
        key = _cache_key(agent_name, prompt)
        await r.set(key, json.dumps(result), ex=ttl)
        logger.debug("Cache SET for %s (ttl=%ds)", key, ttl)
    except Exception:
        logger.debug("Cache set failed", exc_info=True)


# ── Rate limiting ────────────────────────────────────────────────────

_RATE_PREFIX = "nexus:rate:"
_DEFAULT_RATE_LIMIT = 30  # requests per window
_DEFAULT_RATE_WINDOW = 60  # seconds


async def check_rate_limit(
    key: str,
    limit: int = _DEFAULT_RATE_LIMIT,
    window: int = _DEFAULT_RATE_WINDOW,
) -> tuple[bool, int]:
    """Sliding-window rate limiter.

    Args:
        key: Identifier to rate-limit (e.g. IP address, user ID).
        limit: Max requests allowed in the window.
        window: Window size in seconds.

    Returns:
        Tuple of (allowed: bool, remaining: int).
        If allowed is False, the request should be rejected (429).
    """
    try:
        r = await _get_redis()
        rkey = f"{_RATE_PREFIX}{key}"
        current = await r.incr(rkey)
        if current == 1:
            await r.expire(rkey, window)
        remaining = max(0, limit - current)
        return (current <= limit, remaining)
    except Exception:
        # If Redis is down, allow the request (fail-open)
        logger.debug("Rate limit check failed, allowing request", exc_info=True)
        return (True, limit)
