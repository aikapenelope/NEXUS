# NEXUS AI Agent Platform — System Documentation

## Overview

NEXUS is a self-hosted AI agent platform built on **pydantic-deep** (vstorm) and **Pydantic AI**. It runs on a Hetzner CX43 VPS (8 vCPU, 16GB RAM, 150GB disk) and provides autonomous coding agents with planning, filesystem access, shell execution, persistent memory, and real-time streaming.

The platform is designed as a **coding machine** — a self-hosted Devin/Claude Code alternative focused on software engineering tasks.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Hetzner CX43 VPS                          │
│              8 vCPU · 16GB RAM · 150GB disk                  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  nexus-api   │  │  Frontend    │  │  Graphiti MCP    │   │
│  │  FastAPI     │  │  Next.js 15  │  │  FalkorDB +      │   │
│  │  Pydantic AI │  │  CopilotKit  │  │  Knowledge Graph │   │
│  │  :8000       │  │  :3000       │  │  :8001           │   │
│  └──────┬───────┘  └──────────────┘  └──────────────────┘   │
│         │                                                    │
│  ┌──────┴──────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  PostgreSQL  │  │  Redis       │  │  Playwright MCP  │   │
│  │  17+pgvector │  │  7-alpine    │  │  Browser auto    │   │
│  │  :5432       │  │  :6379       │  │  :8931           │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Phoenix     │  │  Prefect     │  │  DockerSandbox   │   │
│  │  Observ.     │  │  Scheduling  │  │  Code execution  │   │
│  │  :6006       │  │  :4200       │  │  (on-demand)     │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Services (10 containers)

| Service | Image | Port | RAM | Purpose |
|---------|-------|------|-----|---------|
| nexus-api | app-nexus-api | 8000 | ~760MB | FastAPI + Pydantic AI + pydantic-deep agents |
| nexus-frontend | app-nexus-frontend | 3000 | ~76MB | Next.js + CopilotKit chat UI + dashboard |
| nexus-postgres | pgvector/pgvector:pg17 | 5432 | ~92MB | Data, Mem0 vectors, Prefect state |
| nexus-redis | redis:7-alpine | 6379 | ~4.5MB | Cache, rate limiting |
| nexus-graphiti | zepai/knowledge-graph-mcp | 8001 | ~256MB | Temporal knowledge graph (FalkorDB + MCP) |
| nexus-playwright | mcp/playwright | 8931 | ~59MB | Headless browser automation (MCP) |
| nexus-phoenix | arizephoenix/phoenix | 6006 | ~285MB | AI observability (OpenTelemetry) |
| nexus-prefect | prefecthq/prefect:3-latest | 4200 | ~177MB | Agent scheduling |
| nexus-sandbox | nexus-sandbox:latest | dynamic | dynamic | Isolated code execution (on-demand) |

**Firewall:** SSH (22) only. All app ports blocked. Access via SSH tunnel.

---

## Agents (10 code-defined)

### Coding Agents (primary)

| Agent | Model | Backend | Features | Budget |
|-------|-------|---------|----------|--------|
| **nexus-developer** | Sonnet (analysis) | DockerSandbox | todo, filesystem, execute, subagents, skills, memory, web, teams, plan | $5.00 / 200K tokens |
| **nexus-coder** | Sonnet (analysis) | DockerSandbox | todo, filesystem, execute, subagents, skills, memory, web | $2.00 / 100K tokens |
| **nexus-reviewer** | Sonnet (analysis) | DockerSandbox | todo, filesystem, memory | $1.00 / 80K tokens |
| **nexus-researcher** | Sonnet (analysis) | DockerSandbox | todo, filesystem, skills, memory, web | $0.50 / 60K tokens |

### General Agents (secondary)

| Agent | Model | Features | Budget |
|-------|-------|----------|--------|
| research-analyst | Sonnet | todo, skills, memory, web | $0.30 / 50K |
| data-analyst | Sonnet | todo, skills, memory, web | $0.30 / 60K |
| content-writer | Groq | todo, skills, memory | $0.05 / 30K |
| social-media | Groq | todo, skills, memory, web | $0.05 / 30K |
| web-monitor | Groq | todo, skills, memory, web | $0.03 / 20K |
| general-assistant | Groq | todo, skills, memory, web, subagents | $0.10 / 40K |

### nexus-developer Subagents

| Subagent | Purpose |
|----------|---------|
| test-writer | Writes comprehensive tests (pytest, jest, go test) |
| reviewer | Code review for bugs, security, quality |
| planner | Analyzes codebase, creates implementation plans, asks questions |

---

## Memory System (4 layers)

| Layer | Technology | Scope | Persistence |
|-------|-----------|-------|-------------|
| **Chat history** | PostgreSQL (nexus_messages) | Per-conversation | Permanent |
| **Semantic memory** | Mem0 + pgvector + Voyage AI | Cross-session facts | Permanent |
| **Agent memory** | MEMORY.md (pydantic-deep) | Per-agent knowledge | Per-backend lifetime |
| **Knowledge graph** | Graphiti + FalkorDB | Temporal entities & relationships | Permanent |

### How memory flows

```
User sends message
  │
  ├─ Layer 1: Load chat history from nexus_messages
  ├─ Layer 2: Search Mem0 for relevant facts → inject in prompt
  ├─ Layer 3: MEMORY.md auto-injected via context_files
  ├─ Layer 4: Graphiti tools available (add_episode, search_facts)
  │
  ▼ Agent executes
  │
  ├─ Post-run: Save messages to chat history
  ├─ Post-run: Extract facts to Mem0
  ├─ Layer 3: Agent updates MEMORY.md via write_memory tool
  └─ Layer 4: Agent stores knowledge via Graphiti MCP tools
```

---

## Toolsets (registered in every agent)

| Toolset | Tools | Source |
|---------|-------|--------|
| **pydantic-deep built-in** | read_file, write_file, edit_file, ls, glob, grep, execute, write_todos, read_todos, save_checkpoint, rewind_to, list_skills, load_skill, read_memory, write_memory, web_search, fetch_url, http_request, task (subagents), spawn_team, assign_task | pydantic-deep framework |
| **brain_toolset** | search_knowledge, read_note, write_note, list_notes | Custom FunctionToolset |
| **remember_toolset** | remember(fact) | Custom FunctionToolset |
| **langchain_tools** | Wikipedia, Arxiv, PubMed | LangChain via Pydantic AI adapter |
| **graphiti_toolset** | add_episode, search_facts, search_nodes, get_episodes | Graphiti MCP server |

### Skills (loaded on-demand)

| Skill | Source | Content |
|-------|--------|---------|
| coding | app/agents/knowledge/coding/ | Engineering workflow, quality standards, testing patterns |
| content | app/agents/knowledge/content/ | Content creation methodology |
| monitoring | app/agents/knowledge/monitoring/ | Web monitoring methodology |
| research | app/agents/knowledge/research/ | Research methodology |
| 11 bundled skills | pydantic-deep package | build-and-compile, code-review, data-formats, environment-discovery, git-workflow, performant-code, refactor, skill-creator, systematic-debugging, test-writer, verification-strategy |

---

## API Endpoints

### REST API (http://localhost:8000)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Liveness check |
| GET | /health/ready | Deep readiness (DB, Redis, MCP) |
| POST | /agents/build | Design agent (architect produces code) |
| POST | /agents/run | Run agent with config + prompt |
| GET | /agents | List all agents (code + DB) |
| POST | /agents | Create agent in DB |
| GET/PATCH/DELETE | /agents/{id} | Agent CRUD |
| POST | /agents/{id}/run | Run saved agent |
| POST | /cerebro/analyze | Multi-model analysis pipeline |
| GET | /runs | List run traces |
| GET | /dashboard/stats | Dashboard metrics |
| GET | /dashboard/monitor | Monitoring data |
| POST | /memory/add | Add to semantic memory |
| POST | /memory/search | Search semantic memory |
| GET/POST | /workflows | Workflow CRUD |
| POST | /workflows/{id}/run | Execute workflow |
| GET | /mcp/servers | List MCP servers |
| POST | /mcp/call | Call MCP tool |

### WebSocket (ws://localhost:8000/ws/agent)

Real-time streaming of agent execution. Protocol:

**Client → Server:**
```json
{"session_id": "xxx", "message": "Fix the auth bug", "agent": "nexus-developer"}
{"cancel": true}
{"approval": {"tool_call_id_123": true}}
```

**Server → Client:**
```json
{"type": "session_created", "session_id": "..."}
{"type": "start"}
{"type": "text_delta", "content": "..."}
{"type": "tool_call_start", "tool_name": "read_file"}
{"type": "tool_args_delta", "args_delta": "..."}
{"type": "tool_start", "tool_name": "read_file", "args": {...}}
{"type": "tool_output", "tool_name": "read_file", "output": "..."}
{"type": "todos_update", "todos": [...]}
{"type": "approval_required", "requests": [{...}]}
{"type": "response", "content": "Done. Fixed the auth bug."}
{"type": "done"}
```

---

## Observability

| System | What it captures | Access |
|--------|-----------------|--------|
| **Logfire** | FastAPI HTTP + Pydantic AI agent runs, tool calls, model requests | logfire-eu.pydantic.dev/nexus/starter-project |
| **Phoenix** | AI-specific traces via OpenTelemetry + OpenInference | localhost:6006 (SSH tunnel) |
| **nexus_runs** | Run history (agent, prompt, output, tokens, latency) | PostgreSQL |
| **nexus_costs** | Cost tracking per run (USD, tokens) | PostgreSQL |

---

## How to Use

### Run a coding task via REST API

```bash
curl -X POST http://localhost:8000/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "name": "nexus-developer",
      "description": "coding agent",
      "instructions": "You are a coding assistant.",
      "role": "analysis",
      "include_todo": true,
      "include_filesystem": true,
      "use_sandbox": false,
      "token_limit": 30000,
      "cost_budget_usd": 0.50
    },
    "prompt": "Write a fibonacci function in Python with tests."
  }'
```

### Run via WebSocket (real-time streaming)

```python
import asyncio, json, websockets

async def run():
    async with websockets.connect("ws://localhost:8000/ws/agent") as ws:
        await ws.send(json.dumps({
            "message": "Fix the failing tests in the auth module",
            "agent": "nexus-developer"
        }))
        async for msg in ws:
            event = json.loads(msg)
            if event["type"] == "text_delta":
                print(event["content"], end="", flush=True)
            elif event["type"] == "tool_start":
                print(f"\n[{event['tool_name']}]")
            elif event["type"] == "done":
                break

asyncio.run(run())
```

### Access services via SSH tunnel

```bash
ssh -L 3000:localhost:3000 \
    -L 8000:localhost:8000 \
    -L 6006:localhost:6006 \
    -L 8001:localhost:8001 \
    root@89.167.96.99
```

Then open:
- Dashboard: http://localhost:3000/dashboard
- API docs: http://localhost:8000/docs
- Phoenix: http://localhost:6006
- Graphiti: http://localhost:8001/health

---

## Production Roadmap: What's Missing for Devin-Level

### Phase 1: Security & Auth (Critical)
- [ ] Tailscale VPN on VPS (replace SSH-only firewall)
- [ ] API authentication (JWT or API key)
- [ ] Real database credentials (not nexus:nexus)
- [ ] Secrets in ESC, not hardcoded in docker-compose
- [ ] CORS restricted to actual domain

### Phase 2: Session Persistence (High)
- [ ] SessionManager with per-user backends (LocalBackend or DockerSandbox)
- [ ] FileCheckpointStore for conversation save/rewind/fork
- [ ] Session resume after disconnect (WebSocket reconnection)
- [ ] Session timeout and cleanup (idle sessions auto-stop)

### Phase 3: GitHub Integration (High)
- [ ] Endpoint: POST /tasks/code — accepts repo URL + task description
- [ ] Auto clone repo into sandbox, run agent, return diff
- [ ] GitHub webhook: assign issue → agent creates PR
- [ ] Branch protection: agent works on feature branches only

### Phase 4: Frontend for Coding (Medium)
- [ ] Rebuild frontend to consume WebSocket streaming
- [ ] Real-time tool call visualization (file tree, terminal output)
- [ ] Approval UI for execute commands
- [ ] Session list with resume capability
- [ ] Diff viewer for code changes

### Phase 5: Multi-User & Scaling (Medium)
- [ ] Per-user session isolation (separate backends)
- [ ] Concurrent agent runs (multiple users)
- [ ] Queue system for long-running tasks (Prefect integration)
- [ ] Resource limits per user (token budgets, sandbox limits)

### Phase 6: Agent Quality (Ongoing)
- [ ] Eval suite: run nexus-developer against SWE-bench subset
- [ ] A/B test different models (Sonnet vs GPT-4.1 vs Groq)
- [ ] Custom skills per project (auto-discover from repo)
- [ ] Agent learning: Graphiti accumulates project knowledge over time
- [ ] Error recovery: auto-retry with different approach on failure

### Phase 7: Deploy Automation (Low)
- [ ] GitHub Actions: push to main → build → deploy to VPS
- [ ] Health check monitoring with alerts
- [ ] Automated backups (Postgres, Graphiti, MEMORY.md)
- [ ] Log aggregation (structured JSON → Loki or similar)

---

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Agent framework | pydantic-deep 0.2.21 (vstorm) on Pydantic AI 1.70 |
| LLM (smart) | Claude Haiku 4.5 via Anthropic |
| LLM (fast) | GPT-OSS 20B via Groq |
| LLM (Graphiti) | GPT-4o-mini via OpenRouter |
| Embeddings (Mem0) | Voyage AI voyage-3-lite |
| Embeddings (Graphiti) | text-embedding-3-small via OpenRouter |
| Knowledge graph | Graphiti + FalkorDB |
| Vector store | pgvector (PostgreSQL 17) |
| Sandbox | DockerSandbox (pydantic-ai-backend) |
| Observability | Logfire + Phoenix (OpenTelemetry) |
| API | FastAPI + WebSocket |
| Frontend | Next.js 15 + CopilotKit + AG-UI |
| Infrastructure | Hetzner Cloud + Pulumi (TypeScript) |
| Secrets | Pulumi ESC |
