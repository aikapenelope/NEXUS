# Workspace Context

This workspace is managed by a NEXUS deep agent.

## Directory Structure

- `/workspace/` - Main working directory for generated files (code, charts, reports)
- `/uploads/` - User-uploaded files (CSV, PDF, images, text)

## Available Capabilities

- **File operations**: read, write, edit, glob, grep files
- **Code execution**: Python code in isolated Docker sandbox
- **Data analysis**: Load the `data-analysis` skill for CSV analysis with pandas and visualization
- **Code review**: Load the `code-review` skill for quality and security review
- **Test generation**: Load the `test-generator` skill for pytest test cases
- **Subagent delegation**: Delegate specialized tasks to subagents

## Stack

- Python 3.12, Pydantic AI, pydantic-deep, FastAPI
- TypeScript, Next.js, CopilotKit, React, Tailwind CSS
- Docker, PostgreSQL 17 + pgvector, Redis 7
- Hetzner Cloud, Pulumi (TypeScript)

## Conventions

- Save all generated files (scripts, charts, reports) to `/workspace/`
- Save charts/visualizations as PNG to `/workspace/`
- Use TODO list to track multi-step tasks
- Load relevant skills before tackling domain-specific tasks
- Follow existing code style and conventions
- Use type hints everywhere (strict pyright compliance)
- Write docstrings for every function and class
