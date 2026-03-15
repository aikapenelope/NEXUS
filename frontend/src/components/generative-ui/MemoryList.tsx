"use client";

import { Database } from "lucide-react";
import type { MemoryEntry } from "@/lib/types";

interface MemoryListProps {
  memories: MemoryEntry[];
}

/** Inline memory search results rendered in the chat. */
export function MemoryList({ memories }: MemoryListProps) {
  if (memories.length === 0) return null;

  return (
    <div className="my-2 p-3 bg-zinc-900 border border-zinc-800 rounded-lg max-w-md">
      <div className="flex items-center gap-2 mb-3">
        <Database className="w-4 h-4 text-blue-400" />
        <span className="text-sm font-medium text-zinc-200">
          Memories ({memories.length})
        </span>
      </div>
      <div className="space-y-2">
        {memories.map((mem) => (
          <div
            key={mem.id}
            className="p-2 bg-zinc-800/50 rounded border border-zinc-700/50"
          >
            <p className="text-sm text-zinc-300">{mem.memory}</p>
            <p className="text-xs text-zinc-500 mt-1">
              Relevance: {(mem.score * 100).toFixed(0)}%
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
