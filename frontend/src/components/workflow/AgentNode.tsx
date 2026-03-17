"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Bot, ShieldCheck } from "lucide-react";

export interface AgentNodeData {
  label: string;
  role: string;
  promptTemplate: string;
  requiresApproval: boolean;
  status: "idle" | "running" | "complete" | "error";
  [key: string]: unknown;
}

const STATUS_STYLES: Record<
  string,
  { border: string; glow: string; badge: string }
> = {
  idle: {
    border: "border-zinc-700",
    glow: "",
    badge: "bg-zinc-800 text-zinc-400",
  },
  running: {
    border: "border-blue-500",
    glow: "shadow-[0_0_12px_rgba(59,130,246,0.3)]",
    badge: "bg-blue-500/20 text-blue-400",
  },
  complete: {
    border: "border-emerald-500",
    glow: "shadow-[0_0_12px_rgba(16,185,129,0.3)]",
    badge: "bg-emerald-500/20 text-emerald-400",
  },
  error: {
    border: "border-red-500",
    glow: "shadow-[0_0_12px_rgba(239,68,68,0.3)]",
    badge: "bg-red-500/20 text-red-400",
  },
};

function AgentNodeComponent({ data }: NodeProps) {
  const nodeData = data as unknown as AgentNodeData;
  const style = STATUS_STYLES[nodeData.status] ?? STATUS_STYLES.idle;

  return (
    <div
      className={`px-4 py-3 rounded-xl bg-zinc-900 border-2 ${style.border} ${style.glow} min-w-[180px] transition-all duration-300`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-zinc-600 !w-2.5 !h-2.5 !border-zinc-800"
      />

      <div className="flex items-center gap-2 mb-1.5">
        <Bot className="w-4 h-4 text-emerald-400 shrink-0" />
        <span className="text-sm font-medium text-zinc-200 truncate">
          {nodeData.label}
        </span>
      </div>

      <div className="flex items-center gap-1.5">
        <span
          className={`px-1.5 py-0.5 text-xs rounded ${style.badge}`}
        >
          {nodeData.role}
        </span>
        {nodeData.requiresApproval && (
          <span className="flex items-center gap-0.5 px-1.5 py-0.5 text-xs rounded bg-amber-500/10 text-amber-400">
            <ShieldCheck className="w-3 h-3" />
            HITL
          </span>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-zinc-600 !w-2.5 !h-2.5 !border-zinc-800"
      />
    </div>
  );
}

export const AgentNode = memo(AgentNodeComponent);
