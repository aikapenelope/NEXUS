# NEXUS

Self-hosted AI agent platform. Build, run, and manage AI agents from natural language — with semantic memory, multi-agent analysis pipelines, browser automation, and workflow orchestration.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Hetzner CX43 VPS                            │
│                 8 vCPU · 16GB RAM · 160GB disk                  │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Frontend     │  │  API         │  │  Playwright MCP      │  │
│  │  Next.js 16   │  │  FastAPI     │  │  Headless Chromium   │  │
│  │  CopilotKit   │  │  Pydantic AI │  │  22 browser tools    │  │
│  │  :3000        │  │  AG-UI       │  │  :8931               │  │
│  │               │  │  :8000       │  │                      │  │
│  └──────┬────────┘  └──────┬───────┘  └──────────────────────┘  │
│         │                  │                                     │
│         │    ┌─────────────┼─────────────┐                      │
│         │    │             │             │                       │
│  ┌──────┴────┴──┐  ┌──────┴──────┐  ┌──┴───────────┐           │
│  │  PostgreSQL   │  │  Redis      │  │  n8n         │           │
│  │  17 + pgvector│  │  7-alpine   │  │  Workflows   │           │
│  │  :5432        │  │  :6379      │  │  MCP hub     │           │
│  │               │  │             │  │  :5678       │           │
│  └──────────────┘  └─────────────┘  └──────────────┘           │
│                                                                 │
│  ┌──────────────┐                                               │
│  │  Prefect      │  Observability: Logfire Cloud (external)     │
│  │  Orchestrator │  Memory: Mem0 + Voyage AI embeddings (API)   │
│  │  :4200        │                                              │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

## Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **nexus-api** | Custom (Python 3.12) | 8000 | FastAPI backend, agent runtime, AG-UI copilot |
| **nexus-frontend** | Custom (Node.js) | 3000 | Next.js 16 + CopilotKit chat UI + dashboard |
| **postgres** | pgvector/pgvector:pg17 | 5432 | Data store, vector embeddings, n8n/Prefect state |
| **redis** | redis:7-alpine | 6379 | Caching, queues, agent state |
| **n8n** | n8nio/n8n:latest | 5678 | Workflow automation, MCP server |
| **playwright** | mcr.microsoft.com/playwright:v1.54.0-noble | 8931 | Headless browser automation (MCP) |
| **prefect** | prefecthq/prefect:3-latest | 4200 | Agent scheduling and orchestration |

Total idle RAM: ~825 MB across 7 containers.

## Core Capabilities

### 1. Agent Builder

Build AI agents from natural language descriptions. The builder agent (Claude Haiku) translates your description into a validated `AgentConfig`, which is then saved to the registry and ready to run.

```bash
curl -X POST http://localhost:8000/agents/build \
  -H "Content-Type: application/json" \
  -d '{"description": "A research agent that summarizes tech news"}'
```

Each agent config includes:
- **Name, description, instructions** (system prompt)
- **Role** — `worker` (Groq, fast/free) or `analysis` (Haiku, smart/paid)
- **Feature toggles** — todo planning, filesystem, sub-agents, skills, memory, web search
- **Limits** — token cap and USD cost budget per run

### 2. Cerebro Pipeline

Multi-agent analysis pipeline inspired by anterior.com. Four sequential stages, each with independent token/cost limits:

| Stage | Model | Purpose |
|-------|-------|---------|
| Research | Groq Llama 3.3 70B | Gather facts, data points, sources |
| Knowledge | Groq Llama 3.3 70B | Organize themes, patterns, context |
| Analysis | Claude Haiku 4.5 | Deep reasoning, risks, opportunities |
| Synthesis | Claude Haiku 4.5 | Executive summary, recommendations |

```bash
curl -X POST http://localhost:8000/cerebro/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "Impact of AI agents on SaaS business models"}'
```

### 3. Semantic Memory (Mem0)

Cross-agent, cross-session memory backed by PostgreSQL + pgvector. Voyage AI provides embeddings (`voyage-3-lite`, 1024 dims) via API — no local model downloads.

```bash
# Add memories
curl -X POST http://localhost:8000/memory/add \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "I prefer Python for data work"}], "user_id": "alice"}'

# Search memories
curl -X POST http://localhost:8000/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "programming preferences", "user_id": "alice"}'
```

When running agents with a `user_id`, relevant memories are automatically injected into the prompt and new conversations are saved back.

### 4. Browser Automation (Playwright MCP)

22 browser tools via Microsoft's Playwright MCP server running headless Chromium. Agents can navigate, click, type, fill forms, take screenshots, evaluate JavaScript, and extract structured data from any web page.

```bash
# List available browser tools
curl http://localhost:8000/mcp/tools?server_name=playwright

# Navigate and snapshot a page
curl -X POST http://localhost:8000/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "browser_navigate", "arguments": {"url": "https://example.com"}, "server_name": "playwright"}'
```

Available tools: `browser_navigate`, `browser_click`, `browser_type`, `browser_fill_form`, `browser_snapshot`, `browser_take_screenshot`, `browser_evaluate`, `browser_run_code`, `browser_drag`, `browser_hover`, `browser_select_option`, `browser_tabs`, `browser_wait_for`, `browser_navigate_back`, `browser_press_key`, `browser_close`, `browser_resize`, `browser_console_messages`, `browser_handle_dialog`, `browser_file_upload`, `browser_install`, `browser_network_requests`.

### 5. MCP Server Registry

Multi-server MCP (Model Context Protocol) registry supporting both SSE and Streamable HTTP transports:

| Server | Transport | URL | Tools |
|--------|-----------|-----|-------|
| n8n | SSE | `http://n8n:5678/mcp` | n8n workflow triggers |
| playwright | Streamable HTTP | `http://playwright:8931/mcp` | 22 browser automation tools |

```bash
# List registered servers
curl http://localhost:8000/mcp/servers

# List tools from a specific server
curl http://localhost:8000/mcp/tools?server_name=playwright
```

### 6. Agent Registry

Persistent storage for agent configurations in PostgreSQL. Agents created via the builder or API are saved with full config, run statistics, and timestamps.

```bash
# List all agents
curl http://localhost:8000/agents

# Run a saved agent by ID
curl -X POST http://localhost:8000/agents/{agent_id}/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize the latest AI news"}'
```

### 7. Dashboard

Langfuse-style observability dashboard at `/dashboard` with three pages:

- **Overview** — Total runs, tokens, agents, average latency, runs-per-day chart, model/source breakdowns
- **Traces** — Full run history with prompt, output, tokens, latency, source, and status
- **Agents** — Registry browser with run stats per agent

### 8. Copilot (AG-UI)

Real-time chat interface powered by CopilotKit + AG-UI protocol. The copilot has 8 tools:

| Tool | Description |
|------|-------------|
| `build_agent` | Build an agent from natural language |
| `run_agent_tool` | Run the last built agent |
| `run_cerebro_tool` | Run the Cerebro analysis pipeline |
| `memory_search_tool` | Search semantic memory |
| `memory_add_tool` | Add information to memory |
| `list_mcp_tools_tool` | List MCP tools from any server |
| `browse_web` | Navigate to URL + get page snapshot |
| `browser_action` | Call any Playwright tool directly |

## Tech Stack

### Backend
- **FastAPI** 0.115+ — async API with auto-generated OpenAPI docs
- **Pydantic AI** 1.68+ — agent framework with structured output, tool calling, usage limits
- **pydantic-deep** 0.2+ — enhanced agents with todo planning, filesystem, sub-agents, web tools
- **Mem0** — semantic memory with fact extraction and vector search
- **asyncpg** — direct PostgreSQL access for registry and traces
- **Logfire** — distributed tracing (auto-instruments Pydantic AI + FastAPI)

### Frontend
- **Next.js** 16 — React framework with App Router
- **CopilotKit** 1.54 — AI copilot UI components
- **AG-UI** — Agent-UI protocol for real-time state streaming
- **recharts** — Dashboard charts
- **Tailwind CSS** — OpenAI-style dark theme (zinc palette, emerald accent)

### Models
| Role | Model | Provider | Use Case |
|------|-------|----------|----------|
| Builder / Analysis | Claude Haiku 4.5 | Anthropic | Structured output, complex reasoning |
| Worker | Llama 3.3 70B | Groq | Research, extraction, cheap tasks |
| Embeddings | voyage-3-lite (1024d) | Voyage AI | Semantic memory vectors |
| Memory LLM | Claude Haiku 4.5 | Anthropic | Fact extraction for Mem0 |

### Infrastructure
- **Hetzner CX43** — 8 vCPU, 16GB RAM, 160GB disk (~$10/mo)
- **Docker Compose** — 7 services, 1 network, 3 volumes
- **Pulumi** — Infrastructure as code (separate repo: `nexus-infra`)
- **Hetzner Cloud Firewall** — Port-level access control

## Project Structure

```
NEXUS/
├── app/
│   ├── agents/
│   │   ├── builder.py      # Meta-agent: NL → AgentConfig (Haiku)
│   │   ├── cerebro.py      # 4-stage analysis pipeline
│   │   └── factory.py      # AgentConfig model + agent instantiation
│   ├── config.py            # Pydantic Settings (env vars)
│   ├── copilot.py           # AG-UI copilot with 8 tools
│   ├── main.py              # FastAPI app, all REST endpoints
│   ├── mcp.py               # Multi-server MCP client registry
│   ├── memory.py            # Mem0 semantic memory service
│   ├── models.py            # Model routing (Haiku vs Groq)
│   ├── registry.py          # Agent CRUD (asyncpg → PostgreSQL)
│   └── traces.py            # Run history + dashboard aggregates
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── api/         # Next.js API routes (proxy to FastAPI)
│       │   ├── dashboard/   # Dashboard pages (overview, traces, agents)
│       │   ├── layout.tsx   # Root layout (dark theme)
│       │   └── page.tsx     # Main chat page
│       ├── components/
│       │   ├── generative-ui/  # AgentCard, CerebroPipelineView, MemoryList
│       │   ├── RightPanel.tsx  # Context panel
│       │   └── Sidebar.tsx     # Navigation sidebar
│       └── lib/             # API client, types, utilities
├── init-db/
│   ├── 01-create-databases.sh
│   ├── 02-nexus-agents.sql  # Agent registry table
│   └── 03-nexus-runs.sql    # Run history table
├── docker-compose.yml       # 7 services stack
├── Dockerfile               # Multi-stage Python 3.12 build
├── pyproject.toml           # Dependencies + tool config
└── .env.example             # Required environment variables
```

## Database Schema

### nexus_agents
Stores agent configurations created by the builder.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR(255) | Agent identifier |
| description | TEXT | What the agent does |
| instructions | TEXT | System prompt |
| role | VARCHAR(50) | `worker`, `analysis`, or `builder` |
| include_todo | BOOLEAN | Task planning enabled |
| include_filesystem | BOOLEAN | File read/write enabled |
| include_subagents | BOOLEAN | Sub-agent delegation enabled |
| include_skills | BOOLEAN | Skill loading enabled |
| include_memory | BOOLEAN | Persistent memory enabled |
| include_web | BOOLEAN | Web search enabled |
| context_manager | BOOLEAN | Auto context compression |
| token_limit | INTEGER | Max tokens per run |
| cost_budget_usd | DOUBLE | Max USD per run |
| total_runs | INTEGER | Lifetime run count |
| total_tokens | INTEGER | Lifetime token usage |
| created_at | TIMESTAMPTZ | Creation timestamp |
| last_run_at | TIMESTAMPTZ | Last execution timestamp |

### nexus_runs
Stores every agent execution for the dashboard traces view.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| agent_id | UUID | FK to nexus_agents (nullable) |
| agent_name | VARCHAR(255) | Agent name at time of run |
| prompt | TEXT | Input prompt |
| output | TEXT | Agent output (truncated to 2000 chars) |
| model | VARCHAR(255) | Model used |
| role | VARCHAR(50) | Agent role |
| input_tokens | INTEGER | Input token count |
| output_tokens | INTEGER | Output token count |
| total_tokens | INTEGER | Total token count |
| latency_ms | INTEGER | Execution time in milliseconds |
| status | VARCHAR(50) | `completed`, `failed` |
| source | VARCHAR(50) | `build`, `run`, `cerebro`, `copilot` |
| created_at | TIMESTAMPTZ | Execution timestamp |

### nexus_memories
Managed by Mem0. Stores vector embeddings (pgvector, 1024 dims) for semantic memory search.

## API Reference

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/docs` | OpenAPI/Swagger UI |

### Agents
| Method | Path | Description |
|--------|------|-------------|
| POST | `/agents/build` | Build agent from natural language |
| POST | `/agents/run` | Run agent with inline config |
| GET | `/agents` | List all saved agents |
| GET | `/agents/{id}` | Get agent by ID |
| POST | `/agents/{id}/run` | Run a saved agent |

### Cerebro
| Method | Path | Description |
|--------|------|-------------|
| POST | `/cerebro/analyze` | Run multi-agent analysis pipeline |

### Memory
| Method | Path | Description |
|--------|------|-------------|
| POST | `/memory/add` | Add conversation to memory |
| POST | `/memory/search` | Search semantic memory |
| GET | `/memory/{user_id}` | List all memories for a user |

### MCP
| Method | Path | Description |
|--------|------|-------------|
| GET | `/mcp/servers` | List registered MCP servers |
| GET | `/mcp/tools` | List tools (query: `server_name`) |
| POST | `/mcp/call` | Call an MCP tool |

### Runs & Dashboard
| Method | Path | Description |
|--------|------|-------------|
| GET | `/runs` | List run traces (query: `agent_id`, `source`) |
| GET | `/runs/{id}` | Get run by ID |
| GET | `/dashboard/stats` | Aggregate dashboard metrics |

### Copilot
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/copilot` | AG-UI copilot endpoint (CopilotKit) |

## Setup

### Prerequisites
- Docker and Docker Compose
- API keys: Anthropic, Groq, Voyage AI

### 1. Clone and configure

```bash
git clone https://github.com/aikapenelope/NEXUS.git
cd NEXUS
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start the stack

```bash
docker compose up -d
```

First start takes a few minutes (Playwright image is ~1.5 GB). Once ready:

- **Frontend**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **Dashboard**: http://localhost:3000/dashboard
- **n8n**: http://localhost:5678
- **Prefect**: http://localhost:4200

### 3. Verify

```bash
# Health check
curl http://localhost:8000/health

# List MCP servers
curl http://localhost:8000/mcp/servers

# List Playwright tools (should return 22)
curl http://localhost:8000/mcp/tools?server_name=playwright
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude Haiku for builder/analysis agents |
| `GROQ_API_KEY` | Yes | Groq Llama for worker agents |
| `VOYAGE_API_KEY` | Yes | Voyage AI for memory embeddings |
| `LOGFIRE_TOKEN` | No | Logfire Cloud for distributed tracing |
| `N8N_PASSWORD` | No | n8n admin password (default: `nexus-n8n`) |

## Configuration

All settings are in `app/config.py` via pydantic-settings (env prefix: `NEXUS_`):

| Setting | Default | Description |
|---------|---------|-------------|
| `haiku_model` | `anthropic:claude-haiku-4-5-20251001` | Smart model |
| `groq_model` | `groq:llama-3.3-70b-versatile` | Fast/cheap model |
| `builder_token_limit` | 16,000 | Builder agent token cap |
| `worker_token_limit` | 8,000 | Worker agent token cap |
| `cerebro_step_token_limit` | 12,000 | Per-stage Cerebro cap |
| `builder_cost_budget` | $0.10 | Builder USD limit |
| `worker_cost_budget` | $0.02 | Worker USD limit |
| `cerebro_cost_budget` | $0.25 | Cerebro USD limit |
| `database_url` | `postgresql://nexus:nexus@localhost:5432/nexus` | PostgreSQL DSN |
| `redis_url` | `redis://localhost:6379/0` | Redis DSN |
| `n8n_mcp_url` | `http://n8n:5678/mcp` | n8n MCP endpoint |
| `playwright_mcp_url` | `http://playwright:8931/mcp` | Playwright MCP endpoint |

## Infrastructure

The VPS infrastructure is managed by Pulumi in a separate repository (`nexus-infra`):

- **Provider**: Hetzner Cloud, location `hel1`
- **Server**: CX43 (8 vCPU, 16GB RAM, 160GB disk), Ubuntu 24.04
- **Network**: Private network 10.1.0.0/16, subnet 10.1.1.0/24
- **Firewall**: Ports 22, 80, 443, 3000, 5678, 8000 open
- **Provisioning**: cloud-init installs Docker CE, configures swap and sysctl

## Development

### Local development (backend)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Type checking
pyright .

# Linting
ruff check .
```

### Local development (frontend)

```bash
cd frontend
npm install
npm run dev
```

## Roadmap

- [x] Phase 1: App skeleton (FastAPI + Pydantic AI + pydantic-deep)
- [x] Phase 2: Mem0 semantic memory + MCP client for n8n
- [x] Phase 2.5: Logfire observability + Voyage AI embeddings
- [x] Phase 3: Next.js frontend with CopilotKit + AG-UI
- [x] Phase 4: Agent Registry + Dashboard
- [x] Phase 5: Browser-Use MCP (Playwright, 22 tools)
- [ ] Phase 6: n8n workflows (create and connect via MCP)
- [ ] Phase 7: Security (Tailscale, firewall hardening, auth)
- [ ] Future: Prefect proactive agents, Graphiti knowledge graph, MinIO storage

## License

MIT
