# ── Stage 1: Build dependencies ──────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools for native extensions (asyncpg, psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# ── Stage 2: Runtime ─────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Runtime deps (libpq for asyncpg/psycopg2, git for repo operations,
# Node.js/npx for MCP servers like server-git and code-context-provider)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl git ca-certificates gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy gunicorn config and application code
COPY gunicorn.conf.py .
COPY app/ ./app/

# Liveness check (lightweight, no external deps)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Gunicorn reads gunicorn.conf.py automatically (workers, logging, timeouts).
CMD ["gunicorn", "app.main:app"]
