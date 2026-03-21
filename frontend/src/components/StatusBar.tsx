"use client";

import { useNexusStore } from "@/stores/nexus";

export function StatusBar() {
  const { sessionId, agent, status, messages } = useNexusStore();

  const statusColor = {
    idle: "text-zinc-500",
    running: "text-emerald-400",
    approval: "text-amber-400",
    done: "text-zinc-400",
    error: "text-red-400",
  }[status];

  return (
    <div className="h-7 flex items-center px-4 border-t border-zinc-800 text-[10px] text-zinc-500 gap-4">
      <span className={statusColor}>{status}</span>
      <span>agent: {agent}</span>
      {sessionId && <span>session: {sessionId.slice(0, 12)}</span>}
      <span>messages: {messages.length}</span>
    </div>
  );
}
