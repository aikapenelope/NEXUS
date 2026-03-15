"use client";

import { Brain, CheckCircle2, Loader2, Circle } from "lucide-react";
import type { CerebroStage } from "@/lib/types";

interface CerebroPipelineViewProps {
  stages: CerebroStage[];
}

/** Inline pipeline progress rendered in the chat during Cerebro analysis. */
export function CerebroPipelineView({ stages }: CerebroPipelineViewProps) {
  if (stages.length === 0) return null;

  return (
    <div className="my-2 p-3 bg-zinc-900 border border-zinc-800 rounded-lg max-w-md">
      <div className="flex items-center gap-2 mb-3">
        <Brain className="w-4 h-4 text-purple-400" />
        <span className="text-sm font-medium text-zinc-200">Cerebro Pipeline</span>
      </div>
      <div className="space-y-2">
        {stages.map((stage, i) => (
          <div key={i} className="flex items-center gap-2">
            {stage.status === "completed" ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : stage.status === "running" ? (
              <Loader2 className="w-4 h-4 text-amber-400 animate-spin shrink-0" />
            ) : (
              <Circle className="w-4 h-4 text-zinc-600 shrink-0" />
            )}
            <span
              className={`text-sm ${
                stage.status === "completed"
                  ? "text-zinc-300"
                  : stage.status === "running"
                    ? "text-zinc-200"
                    : "text-zinc-500"
              }`}
            >
              {stage.name}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
