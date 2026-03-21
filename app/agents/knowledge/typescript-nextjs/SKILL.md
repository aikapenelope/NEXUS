---
name: typescript-nextjs
description: TypeScript + Next.js 15 + CopilotKit + Tailwind CSS patterns
version: 1.0.0
tags:
  - typescript
  - nextjs
  - react
  - tailwind
---

# TypeScript + Next.js Stack

## Runtime
- Next.js 15 with App Router
- TypeScript strict mode
- CopilotKit 1.54 for AI copilot UI
- AG-UI protocol for agent state streaming
- Tailwind CSS with zinc palette + emerald accent
- recharts for dashboard charts

## Project Structure
```
frontend/
  src/
    app/
      api/          # Next.js API routes (proxy to FastAPI)
      dashboard/    # Dashboard pages (overview, traces, agents, tools, workflows)
      layout.tsx    # Root layout (dark theme)
      page.tsx      # Main chat page
    components/
      generative-ui/  # AgentCard, CerebroPipelineView, MemoryList
      workflow/        # WorkflowCanvas, AgentNode
      Sidebar.tsx
      RightPanel.tsx
    lib/
      api.ts        # API client (fetch wrapper)
      types.ts      # TypeScript interfaces
      utils.ts      # Utilities
```

## Conventions
- Named exports, not default exports
- Interfaces over types for object shapes
- Server components by default, 'use client' only when needed
- API routes proxy to FastAPI backend (localhost:8000)
- Tailwind for all styling (no CSS modules)
- camelCase for variables/functions, PascalCase for components

## API Proxy Pattern
```typescript
// frontend/src/app/api/agents/route.ts
export async function GET() {
  const res = await fetch('http://nexus-api:8000/agents');
  const data = await res.json();
  return Response.json(data);
}
```

## Do NOT
- Use CSS modules or styled-components (Tailwind only)
- Create default exports (named exports only)
- Put business logic in API routes (proxy to FastAPI)
- Use class components (functional only)
