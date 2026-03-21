"use client";

import { useState } from "react";
import type { ToolCall } from "@/stores/nexus";

const TOOL_ICONS: Record<string, string> = {
  read_file: "📄",
  write_file: "✏️",
  edit_file: "🔧",
  execute: "▶️",
  grep: "🔍",
  ls: "📁",
  glob: "📁",
  web_search: "🌐",
  fetch_url: "🌐",
  remember_knowledge: "🧠",
  search_knowledge_graph: "🧠",
  remember: "💾",
  write_todos: "📋",
  read_todos: "📋",
  task: "🤖",
  write_memory: "💾",
  read_memory: "💾",
  list_skills: "📚",
  load_skill: "📚",
};

export function ToolCallBlock({ toolCall }: { toolCall: ToolCall }) {
  const [collapsed, setCollapsed] = useState(false);
  const icon = TOOL_ICONS[toolCall.name] ?? "⚙️";
  const isRunning = toolCall.status === "running";

  return (
    <div className="my-1.5 border border-zinc-700/60 rounded-md overflow-hidden bg-zinc-900/50">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-zinc-800/50 transition-colors"
      >
        <span className="text-sm">{icon}</span>
        <span className="font-mono text-emerald-400/90 font-medium">
          {toolCall.name}
        </span>
        {isRunning && (
          <span className="ml-auto flex items-center gap-1.5 text-amber-400/80">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-[10px]">running</span>
          </span>
        )}
        {!isRunning && toolCall.output && (
          <span className="ml-auto text-[10px] text-emerald-500/70">done</span>
        )}
        <span className="text-zinc-600 text-[10px]">
          {collapsed ? "+" : "-"}
        </span>
      </button>

      {!collapsed && (
        <div className="px-3 py-2 text-xs font-mono bg-zinc-950/50 border-t border-zinc-800/50 space-y-1.5">
          {toolCall.args && (
            <div className="text-zinc-500">
              <span className="text-zinc-600 text-[10px] uppercase">
                args:{" "}
              </span>
              <span className="text-zinc-400 break-all">
                {typeof toolCall.args === "string"
                  ? toolCall.args.slice(0, 300)
                  : JSON.stringify(toolCall.args).slice(0, 300)}
                {(toolCall.args?.length ?? 0) > 300 && "..."}
              </span>
            </div>
          )}
          {toolCall.output && (
            <div className="border-t border-zinc-800/50 pt-1.5">
              <span className="text-zinc-600 text-[10px] uppercase">
                output:{" "}
              </span>
              <pre className="whitespace-pre-wrap text-zinc-300 max-h-48 overflow-y-auto mt-0.5">
                {toolCall.output.slice(0, 3000)}
                {toolCall.output.length > 3000 && "\n... (truncated)"}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
