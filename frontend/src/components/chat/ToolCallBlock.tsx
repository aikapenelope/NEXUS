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
  task: "🤖",
};

export function ToolCallBlock({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const icon = TOOL_ICONS[toolCall.name] ?? "⚙️";
  const isRunning = toolCall.status === "running";

  return (
    <div className="my-2 border border-zinc-700 rounded-md overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-xs bg-zinc-900 hover:bg-zinc-800 text-zinc-400"
      >
        <span>{icon}</span>
        <span className="font-mono text-zinc-300">{toolCall.name}</span>
        {isRunning && (
          <span className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        )}
        {!isRunning && (
          <span className="ml-auto text-zinc-600">{expanded ? "▲" : "▼"}</span>
        )}
      </button>

      {(expanded || isRunning) && (
        <div className="px-3 py-2 text-xs font-mono bg-zinc-950 space-y-1">
          {toolCall.args && (
            <div className="text-zinc-500">
              <span className="text-zinc-600">args: </span>
              <span className="text-zinc-400">
                {typeof toolCall.args === "string"
                  ? toolCall.args.slice(0, 200)
                  : JSON.stringify(toolCall.args).slice(0, 200)}
              </span>
            </div>
          )}
          {toolCall.output && (
            <div className="text-zinc-400 border-t border-zinc-800 pt-1 mt-1">
              <pre className="whitespace-pre-wrap max-h-40 overflow-y-auto">
                {toolCall.output.slice(0, 2000)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
