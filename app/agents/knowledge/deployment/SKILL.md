---
name: deployment
description: Docker multi-stage builds, CI/CD pipelines, health checks, rollback strategies, zero-downtime deploys. Use when deploying or configuring deployment infrastructure.
version: 1.0.0
tags:
  - deployment
  - docker
  - cicd
  - health-checks
  - rollback
---

# Deployment

## Docker Multi-Stage Build
```dockerfile
# Stage 1: Build
FROM python:3.12-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y gcc libpq-dev
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime (minimal)
FROM python:3.12-slim
COPY --from=builder /install /usr/local
COPY app/ ./app/
CMD ["gunicorn", "app.main:app"]
```

## Health Checks
```yaml
# docker-compose.yml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
  interval: 30s
  timeout: 10s
  start_period: 60s
  retries: 5
```

```python
# Endpoint
@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.5.0"}

@app.get("/health/ready")
async def readiness():
    # Check DB, Redis, external services
    db_ok = await check_db()
    redis_ok = await check_redis()
    return {"db": db_ok, "redis": redis_ok}
```

## CI/CD Pipeline (GitHub Actions)
```yaml
name: CI/CD
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e ".[dev]"
      - run: ruff check app/
      - run: pyright app/

  deploy:
    needs: lint
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/app && git pull
            docker compose up -d --build
            sleep 30 && curl -sf http://localhost:8000/health
```

## Rollback Strategy
```bash
# Quick rollback: revert to previous image
docker compose down
git checkout HEAD~1
docker compose up -d --build

# Or use tagged images
docker tag app:latest app:rollback
# ... deploy new version ...
# If broken:
docker tag app:rollback app:latest
docker compose up -d
```

## Zero-Downtime Deploy
```yaml
# docker-compose.yml
services:
  api:
    deploy:
      update_config:
        order: start-first    # Start new before stopping old
        failure_action: rollback
```

## Log Rotation
```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

## Do NOT
- Deploy without health checks
- Skip CI on "small changes"
- Deploy to production on Friday
- Use `latest` tag in production (use commit SHA)
- Store secrets in docker-compose.yml (use env files or ESC)
