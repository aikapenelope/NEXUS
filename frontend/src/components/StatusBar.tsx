"use client";

import { useNexusStore } from "@/stores/nexus";

export function StatusBar() {
  const sessionId = useNexusStore((s) => s.sessionId);
  const agent = useNexusStore((s) => s.agent);
  const status = useNexusStore((s) => s.status);
  const messages = useNexusStore((s) => s.messages);
  const currentToolCalls = useNexusStore((s) => s.currentToolCalls);

  const statusColor: Record<string, string> = {
    idle: "text-zinc-500",
    running: "text-emerald-400",
    approval: "text-amber-400",
    done: "text-zinc-400",
    error: "text-red-400",
  };

  const toolsRunning = currentToolCalls.filter(
    (tc) => tc.status === "running",
  ).length;

  return (
    <div className="h-7 flex items-center px-4 border-t border-zinc-800 text-[10px] text-zinc-500 gap-4 bg-zinc-950">
      <span className={`font-medium ${statusColor[status] ?? "text-zinc-500"}`}>
        {status === "running" && toolsRunning > 0
          ? `running (${toolsRunning} tool${toolsRunning > 1 ? "s" : ""})`
          : status}
      </span>
      <span className="text-zinc-600">|</span>
      <span>{agent}</span>
      {sessionId && (
        <>
          <span className="text-zinc-600">|</span>
          <span>session: {sessionId.slice(0, 12)}</span>
        </>
      )}
      <span className="text-zinc-600">|</span>
      <span>{messages.length} messages</span>
    </div>
  );
}
