"use client";

import { Bot, Cpu, Wrench } from "lucide-react";
import type { AgentInfo } from "@/lib/types";

interface AgentCardProps {
  agent: AgentInfo;
}

/** Inline card rendered in the chat when an agent is built or updated. */
export function AgentCard({ agent }: AgentCardProps) {
  const statusColor =
    agent.status === "ready"
      ? "text-emerald-400"
      : agent.status === "building"
        ? "text-amber-400"
        : agent.status === "running"
          ? "text-blue-400"
          : "text-zinc-400";

  return (
    <div className="my-2 p-3 bg-zinc-900 border border-zinc-800 rounded-lg max-w-md">
      <div className="flex items-center gap-2 mb-2">
        <Bot className="w-4 h-4 text-emerald-400" />
        <span className="text-sm font-medium text-zinc-200">{agent.name || "Unnamed Agent"}</span>
        <span className={`text-xs ml-auto ${statusColor}`}>{agent.status}</span>
      </div>
      {agent.role && (
        <p className="text-xs text-zinc-400 mb-2">{agent.role}</p>
      )}
      <div className="flex items-center gap-3 text-xs text-zinc-500">
        <span className="flex items-center gap-1">
          <Cpu className="w-3 h-3" /> {agent.model || "—"}
        </span>
        {agent.tools.length > 0 && (
          <span className="flex items-center gap-1">
            <Wrench className="w-3 h-3" /> {agent.tools.length} tools
          </span>
        )}
      </div>
    </div>
  );
}
