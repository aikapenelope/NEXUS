# NEXUS — Self-Hosted Coding Machine

A personal Devin/Claude Code alternative. Autonomous coding agents that plan, write, test, and ship code on your own infrastructure.

Built on [pydantic-deep](https://github.com/vstorm-co/pydantic-deepagents) (vstorm) + [Pydantic AI](https://ai.pydantic.dev). Runs on a single Hetzner VPS.

## What It Does

Give NEXUS a task. It clones your repo, understands the codebase, writes code, runs tests, fixes errors, and returns a diff. No IDE plugins, no cloud lock-in, no per-seat pricing.

```bash
# Via API
curl -X POST http://localhost:8000/tasks/code \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/you/project.git", "task": "Add type hints to auth.py and fix all pyright errors"}'

# Response: { status, output, diff, files_changed, tokens_used }
```

```
# Via WebSocket (real-time streaming)
ws://localhost:8000/ws/agent
→ Send: {"message": "Create a REST API with FastAPI", "agent": "nexus-developer"}
← Receive: tool_call_start, tool_args_delta, tool_output, text_delta, response, done
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Hetzner CX43 VPS                          │
│              8 vCPU · 16GB RAM · 150GB disk                  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  nexus-api   │  │  Frontend    │  │  Graphiti        │  │
│  │  FastAPI     │  │  Next.js 15  │  │  FalkorDB +      │  │
│  │  Pydantic AI │  │  WebSocket   │  │  Knowledge Graph │  │
│  │  :8000       │  │  :3000       │  │  :8001           │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  PostgreSQL  │  │  Redis       │  │  Playwright      │  │
│  │  17+pgvector │  │  7-alpine    │  │  Browser auto    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Phoenix     │  │  Prefect     │  │  DockerSandbox   │  │
│  │  Observ.     │  │  Scheduling  │  │  Code execution  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

8 containers. SSH-only firewall. All app ports internal.

## Capabilities

### Coding Agent (nexus-developer)
- **Plans before acting** — creates todo list, executes step by step
- **Reads and writes files** — read_file, write_file, edit_file, grep, glob, ls
- **Executes commands** — python3, pytest, ruff, pip install (auto-approved)
- **Type checks code** — check_types (pyright) and check_lint (ruff) after edits
- **Delegates to subagents** — test-writer, reviewer, planner
- **Remembers across sessions** — 4-layer memory (chat history, Mem0, MEMORY.md, Graphiti)
- **Understands repos** — auto-indexes structure, reads key files
- **Streams in real-time** — WebSocket with tool calls, args, output, todos

### 10 Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| nexus-developer | Haiku 4.5 | Full coding: plan, write, test, ship |
| nexus-coder | Haiku 4.5 | Fast code generation |
| nexus-reviewer | Haiku 4.5 | Code review, security, quality |
| nexus-researcher | Haiku 4.5 | Research docs, APIs, best practices |
| research-analyst | Haiku 4.5 | Deep multi-source research |
| data-analyst | Haiku 4.5 | Data analysis, statistics |
| content-writer | Groq | Content creation |
| web-monitor | Groq | Web change tracking |
| social-media | Groq | Social media content |
| general-assistant | Groq | General tasks |

### 9 Toolsets

| Toolset | Tools |
|---------|-------|
| pydantic-deep | read/write/edit files, execute, todos, checkpoints, skills, memory, web search |
| graphiti | remember_knowledge, search_knowledge_graph (temporal knowledge graph) |
| lsp | check_types (pyright), check_lint (ruff) |
| brain | search_knowledge, read/write/list notes |
| remember | remember(fact) → Mem0 semantic memory |
| langchain | Wikipedia, Arxiv, PubMed |
| github | repos, issues, PRs, files, branches (MCP) |
| git | status, diff, log, commit, branch (MCP) |
| playwright | navigate, click, fill, screenshot (MCP) |

### 20 Skills (progressive disclosure — loaded on demand)

| Skill | What it teaches the agent |
|-------|--------------------------|
| coding | Engineering workflow, quality standards, testing |
| python-fastapi | Python 3.12, FastAPI, Pydantic AI, asyncpg |
| typescript-nextjs | Next.js 15, App Router, CopilotKit, Tailwind |
| docker-infra | Docker Compose, networking, volumes |
| hetzner-platform | Hetzner Cloud, Pulumi, 3-plane architecture |
| postgres-pgvector | PostgreSQL 17, asyncpg, vector operations |
| content | Content creation methodology |
| monitoring | Web monitoring, change detection |
| research | Research methodology, source verification |
| +11 bundled | code-review, git-workflow, refactor, test-writer, systematic-debugging, etc. |

### Memory (4 layers)

| Layer | Technology | Persistence |
|-------|-----------|-------------|
| Chat history | PostgreSQL | Permanent |
| Semantic memory | Mem0 + pgvector + Voyage AI | Permanent |
| Agent memory | MEMORY.md | Per-session |
| Knowledge graph | Graphiti + FalkorDB | Permanent, temporal |

## How to Use

### 1. WebSocket Chat (Frontend)

Access via SSH tunnel:
```bash
ssh -L 3000:localhost:3000 -L 8000:localhost:8000 root@YOUR_VPS_IP
```
Open `http://localhost:3000`. Select an agent. Type a task.

The UI shows:
- Real-time text streaming
- Tool call blocks (write_file, execute, check_types) with args and output
- Right panel: Tools history, Terminal output, Files changed, Todos, Session info
- Token count and cost per message

### 2. Code Task API (Devin-style)

```bash
curl -X POST http://localhost:8000/tasks/code \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/you/project.git",
    "task": "Write pytest tests for the auth module",
    "branch": "main",
    "token_limit": 100000,
    "cost_budget_usd": 0.50
  }'
```

The agent:
1. Clones the repo into an isolated session workspace
2. Auto-indexes the repo structure
3. Executes the task (write files, run commands, iterate)
4. Returns: output, diff, files_changed, tokens_used

### 3. Direct Agent Run

```bash
curl -X POST http://localhost:8000/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "name": "nexus-developer",
      "role": "analysis",
      "include_todo": true,
      "include_filesystem": true,
      "token_limit": 30000
    },
    "prompt": "Write a fibonacci function with tests"
  }'
```

### 4. Eval Suite

```bash
python evals/run_eval.py --api http://localhost:8000
```

5 tasks of increasing difficulty: type-hints, write-tests, fix-lint, health-endpoint, refactor-tools.

## Setup

### Prerequisites
- Hetzner CX43 VPS (or any server with 8GB+ RAM, Docker)
- Anthropic API key (Claude Haiku 4.5)
- Groq API key (GPT-OSS 20B)
- Pulumi for infrastructure (optional)

### Deploy

```bash
# Clone
git clone https://github.com/aikapenelope/NEXUS.git
cd NEXUS

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
docker compose up -d

# Verify
curl http://localhost:8000/health
```

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| ANTHROPIC_API_KEY | Yes | Claude Haiku 4.5 (smart agent) |
| GROQ_API_KEY | Yes | Groq GPT-OSS 20B (fast agent) |
| VOYAGE_API_KEY | Yes | Voyage AI embeddings (Mem0) |
| OPENAI_API_KEY | Yes | OpenRouter for Graphiti (gpt-4o-mini + embeddings) |
| LOGFIRE_TOKEN | Optional | Pydantic Logfire observability |
| GITHUB_PERSONAL_ACCESS_TOKEN | Optional | GitHub MCP tools |

## What's Still Missing (vs Devin)

| Capability | NEXUS | Devin |
|-----------|-------|-------|
| Plan + execute + iterate | Yes | Yes |
| File operations | Yes | Yes |
| Shell execution | Yes (auto-approve) | Yes |
| Subagent delegation | Yes | Yes |
| Type checking feedback | Yes (pyright/ruff) | Yes (native LSP) |
| Knowledge graph memory | Yes (Graphiti) | No |
| WebSocket streaming | Yes | Yes |
| Prompt caching | Yes (Anthropic) | Yes |
| Browser testing | Partial (Playwright MCP) | Yes (native) |
| IDE integration | No | Yes (acquired Windsurf) |
| Cloud sandbox | No (local Docker) | Yes (managed) |
| PR auto-creation | Partial (Git MCP) | Yes (native) |
| Multi-user | Partial (user_id) | Yes |
| Auth/security | No (SSH only) | Yes |
| Eval benchmarks | 0/5 pass (token overhead) | 67% on defined tasks |

### Priority improvements
1. **Reduce token overhead** — agent spends ~40K tokens on simple tasks due to system prompt size. Prompt caching helps but the base cost is still high.
2. **Run eval suite** — measure and iterate on pass rate
3. **Auth + security** — API keys, real DB credentials, Tailscale VPN
4. **GitHub webhook** — assign issue → agent creates PR

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | pydantic-deep 0.2.21 on Pydantic AI 1.70 |
| LLM (smart) | Claude Haiku 4.5 via Anthropic |
| LLM (fast) | GPT-OSS 20B via Groq |
| LLM (Graphiti) | GPT-4o-mini via OpenRouter |
| Embeddings | Voyage AI voyage-3-lite + text-embedding-3-small |
| Knowledge graph | Graphiti + FalkorDB |
| Vector store | pgvector (PostgreSQL 17) |
| Observability | Logfire (Pydantic) |
| API | FastAPI + WebSocket |
| Frontend | Next.js 15 + Tailwind + zustand |
| Infrastructure | Hetzner Cloud + Pulumi (TypeScript) |
| Secrets | Pulumi ESC |
| CI/CD | GitHub Actions (lint + deploy) |

## License

MIT
