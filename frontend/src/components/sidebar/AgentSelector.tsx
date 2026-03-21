"use client";

import { useNexusStore } from "@/stores/nexus";

const AGENTS = [
  { id: "nexus-developer", label: "Developer", desc: "Full coding agent" },
  { id: "nexus-coder", label: "Coder", desc: "Fast code generation" },
  { id: "nexus-reviewer", label: "Reviewer", desc: "Code review" },
  { id: "nexus-researcher", label: "Researcher", desc: "Research & docs" },
  { id: "general-assistant", label: "Assistant", desc: "General tasks" },
];

export function AgentSelector() {
  const { agent, setAgent, status } = useNexusStore();

  return (
    <div className="p-3">
      <p className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">
        Agent
      </p>
      <div className="space-y-1">
        {AGENTS.map((a) => (
          <button
            key={a.id}
            onClick={() => status !== "running" && setAgent(a.id)}
            className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
              agent === a.id
                ? "bg-emerald-900/40 text-emerald-300"
                : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            }`}
          >
            <div className="font-medium">{a.label}</div>
            <div className="text-[10px] text-zinc-500">{a.desc}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
