"use client";

import { useNexusStore } from "@/stores/nexus";
import { useAgentStream } from "@/hooks/useAgentStream";

export function ApprovalModal() {
  const { pendingApprovals } = useNexusStore();
  const { approve } = useAgentStream();

  if (pendingApprovals.length === 0) return null;

  return (
    <div className="my-3 border border-amber-800/60 rounded-lg bg-amber-950/30 p-4">
      <p className="text-xs font-medium text-amber-300 mb-3">
        Approval required
      </p>
      {pendingApprovals.map((req) => (
        <div key={req.tool_call_id} className="mb-3 last:mb-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-mono text-zinc-300">
              {req.tool_name}
            </span>
            <span className="text-xs text-zinc-500">
              {typeof req.args === "string"
                ? req.args.slice(0, 120)
                : JSON.stringify(req.args).slice(0, 120)}
            </span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => approve(req.tool_call_id, true)}
              className="px-3 py-1 text-xs bg-emerald-900/60 text-emerald-200 rounded hover:bg-emerald-900/80"
            >
              Approve
            </button>
            <button
              onClick={() => approve(req.tool_call_id, false)}
              className="px-3 py-1 text-xs bg-red-900/60 text-red-200 rounded hover:bg-red-900/80"
            >
              Deny
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
