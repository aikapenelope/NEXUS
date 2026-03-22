"use client";

import { useState } from "react";
import { useNexusStore } from "@/stores/nexus";
import { TodoProgress } from "./TodoProgress";

type Tab = "tools" | "todos" | "info";

export function RightPanel() {
  const [activeTab, setActiveTab] = useState<Tab>("tools");
  const messages = useNexusStore((s) => s.messages);
  const todos = useNexusStore((s) => s.todos);
  const agent = useNexusStore((s) => s.agent);
  const sessionId = useNexusStore((s) => s.sessionId);
  const status = useNexusStore((s) => s.status);

  // Collect all tool calls from all messages
  const allToolCalls = messages.flatMap((m) => m.toolCalls ?? []);
  const totalTokens = messages.length * 5000; // rough estimate

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "tools", label: "Tools", count: allToolCalls.length },
    { id: "todos", label: "Todos", count: todos.length },
    { id: "info", label: "Info" },
  ];

  return (
    <aside className="w-72 border-l border-zinc-800 flex flex-col bg-zinc-950">
      {/* Tab bar */}
      <div className="h-12 flex items-center border-b border-zinc-800 px-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 text-[11px] rounded transition-colors ${
              activeTab === tab.id
                ? "bg-zinc-800 text-zinc-200"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span className="ml-1 text-[9px] text-zinc-500">
                ({tab.count})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-3">
        {activeTab === "tools" && (
          <div className="space-y-2">
            {allToolCalls.length === 0 ? (
              <p className="text-xs text-zinc-600 text-center mt-8">
                No tool calls yet
              </p>
            ) : (
              allToolCalls.map((tc, i) => (
                <div
                  key={`${tc.id}-${i}`}
                  className="border border-zinc-800 rounded p-2 text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-emerald-400">
                      {tc.name}
                    </span>
                    <span
                      className={`text-[9px] px-1 rounded ${
                        tc.status === "done"
                          ? "bg-emerald-900/40 text-emerald-400"
                          : "bg-amber-900/40 text-amber-400"
                      }`}
                    >
                      {tc.status}
                    </span>
                  </div>
                  {tc.output && (
                    <pre className="text-zinc-500 mt-1 text-[10px] max-h-20 overflow-hidden">
                      {tc.output.slice(0, 200)}
                    </pre>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === "todos" && <TodoProgress />}

        {activeTab === "info" && (
          <div className="space-y-3 text-xs">
            <div>
              <p className="text-zinc-500 text-[10px] uppercase mb-1">Agent</p>
              <p className="text-zinc-300">{agent}</p>
            </div>
            <div>
              <p className="text-zinc-500 text-[10px] uppercase mb-1">
                Session
              </p>
              <p className="text-zinc-300 font-mono text-[10px]">
                {sessionId ?? "none"}
              </p>
            </div>
            <div>
              <p className="text-zinc-500 text-[10px] uppercase mb-1">
                Status
              </p>
              <p
                className={`${
                  status === "running"
                    ? "text-emerald-400"
                    : status === "error"
                      ? "text-red-400"
                      : "text-zinc-300"
                }`}
              >
                {status}
              </p>
            </div>
            <div>
              <p className="text-zinc-500 text-[10px] uppercase mb-1">
                Messages
              </p>
              <p className="text-zinc-300">{messages.length}</p>
            </div>
            <div>
              <p className="text-zinc-500 text-[10px] uppercase mb-1">
                Tool Calls
              </p>
              <p className="text-zinc-300">{allToolCalls.length}</p>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
