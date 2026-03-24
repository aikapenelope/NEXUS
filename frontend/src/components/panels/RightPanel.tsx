"use client";

import { useState } from "react";
import { useNexusStore } from "@/stores/nexus";
import { TodoProgress } from "./TodoProgress";
import { TerminalView } from "./TerminalView";
import { DiffViewer } from "./DiffViewer";
import { FileTree } from "./FileTree";

type Tab = "tools" | "terminal" | "files" | "todos" | "info";

export function RightPanel() {
  const [activeTab, setActiveTab] = useState<Tab>("tools");
  const messages = useNexusStore((s) => s.messages);
  const todos = useNexusStore((s) => s.todos);
  const agent = useNexusStore((s) => s.agent);
  const sessionId = useNexusStore((s) => s.sessionId);
  const status = useNexusStore((s) => s.status);

  // Collect all tool calls from all messages
  const allToolCalls = messages.flatMap((m) => m.toolCalls ?? []);

  // Extract execute outputs for terminal view
  const executeOutputs = allToolCalls
    .filter((tc) => tc.name === "execute" && tc.output)
    .map((tc) => tc.output ?? "")
    .join("\n---\n");

  // Extract file paths from write_file outputs
  const changedFiles = allToolCalls
    .filter((tc) => tc.name === "write_file" && tc.output)
    .map((tc) => {
      const match = tc.output?.match(/to (.+)$/);
      return match ? match[1] : tc.output ?? "";
    });

  // Extract diffs from tool outputs (git diff)
  const diffs = allToolCalls
    .filter(
      (tc) =>
        tc.name === "execute" &&
        tc.output &&
        (tc.output.includes("diff --git") || tc.output.includes("@@")),
    )
    .map((tc) => tc.output ?? "")
    .join("\n");

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "tools", label: "Tools", count: allToolCalls.length },
    { id: "terminal", label: "Term" },
    { id: "files", label: "Files", count: changedFiles.length },
    { id: "todos", label: "Todos", count: todos.length },
    { id: "info", label: "Info" },
  ];

  return (
    <aside className="w-72 border-l border-zinc-800 flex flex-col bg-zinc-950">
      {/* Tab bar */}
      <div className="h-12 flex items-center border-b border-zinc-800 px-1 gap-0.5">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-2 py-1.5 text-[10px] rounded transition-colors ${
              activeTab === tab.id
                ? "bg-zinc-800 text-zinc-200"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span className="ml-0.5 text-[9px] text-zinc-600">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === "tools" && (
          <div className="p-3 space-y-2">
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

        {activeTab === "terminal" && <TerminalView output={executeOutputs} />}

        {activeTab === "files" && <FileTree files={changedFiles} />}

        {activeTab === "todos" && (
          <div className="p-3">
            <TodoProgress />
          </div>
        )}

        {activeTab === "info" && (
          <div className="p-3 space-y-3 text-xs">
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
                className={
                  status === "running"
                    ? "text-emerald-400"
                    : status === "error"
                      ? "text-red-400"
                      : "text-zinc-300"
                }
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
            {diffs && (
              <div>
                <p className="text-zinc-500 text-[10px] uppercase mb-1">
                  Diff
                </p>
                <DiffViewer diff={diffs} />
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
