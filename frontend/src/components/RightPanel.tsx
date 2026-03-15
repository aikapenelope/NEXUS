"use client";

import { Bot, Brain, Database } from "lucide-react";
import type { NexusState } from "@/lib/types";

interface RightPanelProps {
  state: NexusState | undefined;
}

export function RightPanel({ state }: RightPanelProps) {
  if (!state) return null;

  const panel = state.active_panel;
  if (panel === "chat") return null;

  return (
    <aside className="w-80 border-l border-zinc-800 bg-zinc-950 overflow-y-auto">
      <div className="p-4">
        {panel === "agents" && <AgentPanel state={state} />}
        {panel === "cerebro" && <CerebroPanel state={state} />}
        {panel === "memory" && <MemoryPanel state={state} />}
      </div>
    </aside>
  );
}

function AgentPanel({ state }: { state: NexusState }) {
  const agent = state.current_agent;
  if (!agent.name) {
    return (
      <div className="text-zinc-500 text-sm">
        <Bot className="w-5 h-5 mb-2" />
        No agent built yet. Ask NEXUS to build one.
      </div>
    );
  }
  return (
    <div>
      <h3 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
        <Bot className="w-4 h-4" /> Agent Details
      </h3>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-zinc-500">Name</span>
          <span className="text-zinc-200">{agent.name}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-500">Model</span>
          <span className="text-zinc-200">{agent.model}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-500">Status</span>
          <span className={agent.status === "ready" ? "text-emerald-400" : "text-zinc-400"}>
            {agent.status}
          </span>
        </div>
        {agent.tools.length > 0 && (
          <div>
            <span className="text-zinc-500">Tools</span>
            <div className="mt-1 flex flex-wrap gap-1">
              {agent.tools.map((tool) => (
                <span key={tool} className="px-2 py-0.5 bg-zinc-800 rounded text-xs text-zinc-300">
                  {tool}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CerebroPanel({ state }: { state: NexusState }) {
  const stages = state.cerebro_stages;
  if (stages.length === 0) {
    return (
      <div className="text-zinc-500 text-sm">
        <Brain className="w-5 h-5 mb-2" />
        No Cerebro pipeline running. Ask NEXUS to analyze a topic.
      </div>
    );
  }
  return (
    <div>
      <h3 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
        <Brain className="w-4 h-4" /> Cerebro Pipeline
      </h3>
      <div className="space-y-3">
        {stages.map((stage, i) => (
          <div key={i} className="flex items-start gap-2">
            <div
              className={`w-2 h-2 rounded-full mt-1.5 ${
                stage.status === "completed"
                  ? "bg-emerald-400"
                  : stage.status === "running"
                    ? "bg-amber-400 animate-pulse"
                    : "bg-zinc-600"
              }`}
            />
            <div className="flex-1 min-w-0">
              <div className="text-sm text-zinc-300">{stage.name}</div>
              {stage.output && (
                <div className="text-xs text-zinc-500 mt-0.5 truncate">{stage.output}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MemoryPanel({ state }: { state: NexusState }) {
  const memories = state.memories;
  if (memories.length === 0) {
    return (
      <div className="text-zinc-500 text-sm">
        <Database className="w-5 h-5 mb-2" />
        No memories loaded. Ask NEXUS to search memory.
      </div>
    );
  }
  return (
    <div>
      <h3 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
        <Database className="w-4 h-4" /> Memories ({memories.length})
      </h3>
      <div className="space-y-2">
        {memories.map((mem) => (
          <div key={mem.id} className="p-2 bg-zinc-900 rounded border border-zinc-800">
            <div className="text-sm text-zinc-300">{mem.memory}</div>
            <div className="text-xs text-zinc-500 mt-1">
              Score: {mem.score.toFixed(2)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
