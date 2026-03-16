"""Gunicorn configuration for NEXUS API.

Loaded automatically when gunicorn finds gunicorn.conf.py in the working dir.
Configures JSON-formatted access logs for structured log aggregation.
"""

import os

# ── Workers ──────────────────────────────────────────────────────────
# UvicornWorker: each worker gets its own async event loop.
# No --preload to avoid sharing global state (asyncpg pools, etc.).
workers = int(os.environ.get("GUNICORN_WORKERS", "4"))
worker_class = "uvicorn.workers.UvicornWorker"
bind = "0.0.0.0:8000"

# ── Timeouts ─────────────────────────────────────────────────────────
timeout = 120  # Deep agent runs can take a while
graceful_timeout = 30
keepalive = 5

# ── Logging ──────────────────────────────────────────────────────────
# JSON access log format for structured logging.
# Fields: timestamp, method, path, status, response_time_ms, bytes.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")

# JSON-ish structured access log (one-line, parseable by Docker/Loki/etc.)
access_log_format = (
    '{"timestamp":"%(t)s","method":"%(m)s","path":"%(U)s",'
    '"query":"%(q)s","status":"%(s)s","response_time_ms":"%(M)s",'
    '"bytes":"%(B)s","remote_addr":"%(h)s","user_agent":"%(a)s"}'
)
