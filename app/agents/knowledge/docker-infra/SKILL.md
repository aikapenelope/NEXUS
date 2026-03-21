---
name: docker-infra
description: Docker Compose infrastructure for NEXUS and platform-infra services
version: 1.0.0
tags:
  - docker
  - infrastructure
  - containers
  - compose
---

# Docker & Container Infrastructure

## NEXUS Stack (CX43 VPS — 8 vCPU, 16GB RAM, 150GB)

### Services (docker-compose.yml)
| Service | Image | Port | RAM Limit | Purpose |
|---------|-------|------|-----------|---------|
| nexus-api | app-nexus-api (custom) | 8000 | 4GB | FastAPI + agents |
| nexus-frontend | app-nexus-frontend (custom) | 3000 | 512MB | Next.js dashboard |
| nexus-postgres | pgvector/pgvector:pg17 | 5432 (local) | 2GB | Data + vectors |
| nexus-redis | redis:7-alpine | 6379 (local) | 256MB | Cache |
| nexus-graphiti | zepai/knowledge-graph-mcp | 8001/6380 | 512MB | Knowledge graph |
| nexus-playwright | mcp/playwright | 8931 | 2GB | Browser automation |
| nexus-phoenix | arizephoenix/phoenix | 6006 | 1GB | AI observability |
| nexus-prefect | prefecthq/prefect:3-latest | 4200 (local) | 512MB | Scheduling |
| nexus-sandbox | nexus-sandbox (custom) | dynamic | dynamic | Code execution |

### Networking
- All services on `nexus-net` bridge network
- Postgres, Redis, Prefect bind to 127.0.0.1 only
- Firewall: SSH (22) only, all app ports blocked

### Volumes
- postgres-data, redis-data, phoenix-data, graphiti-data
- /opt/nexus/data/sessions (host mount for session persistence)
- /var/run/docker.sock (for sandbox container creation)

### Build Patterns
```yaml
# Custom image build
nexus-api:
  build: .
  container_name: nexus-api

# Health checks
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U nexus"]
  interval: 10s
  timeout: 5s
  retries: 5

# Log rotation
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

## Platform-Infra Stack (Hetzner hel1)

### Architecture (3 planes)
| Plane | Server | Specs | IP | Role |
|-------|--------|-------|-----|------|
| Control | cx23 | 3 vCPU, 4GB | 10.0.1.10 | Coolify, Traefik, monitoring |
| Data | cx33 | 4 vCPU, 8GB | 10.0.1.20 | PostgreSQL 16+pgvector, PgBouncer, Redis 7, MinIO |
| App A | cx33 | 4 vCPU, 8GB | 10.0.1.30 | App containers via Coolify |

### Hosted Projects
- **Whabi**: WhatsApp Business CRM (Redis DB 0, MinIO: whabi-media, whabi-documents)
- **Docflow**: EHR system (Redis DB 1, MinIO: docflow-documents)
- **Aurora**: Voice-first PWA (Nuxt 3 + Clerk + Groq Whisper, Redis DB 2, MinIO: aurora-assets)

### Network
- Private: 10.0.0.0/16, subnet 10.0.1.0/24, zone eu-central
- Access: Tailscale VPN only (no public SSH)
- Managed by Pulumi (TypeScript) in platform-infra repo

## Do NOT
- Expose database ports to public network
- Run containers without memory limits
- Mount Docker socket without understanding security implications
- Change docker-compose.yml without checking resource impact
