"use client";

import { useEffect, useState, useCallback } from "react";
import {
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Bot,
  Clock,
  Hash,
  Zap,
} from "lucide-react";
import type { RegistryAgent } from "@/lib/types";

// ── Types ───────────────────────────────────────────────────────────

interface RunTrace {
  id: string;
  agent_name: string;
  prompt: string;
  output: string;
  model: string;
  total_tokens: number;
  latency_ms: number;
  status: string;
  source: string;
  created_at: string;
}

// ── Page ────────────────────────────────────────────────────────────

export default function AgentsPage() {
  const [agents, setAgents] = useState<RegistryAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [agentRuns, setAgentRuns] = useState<RunTrace[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);

  const loadAgents = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/agents");
      if (res.ok) {
        const data = await res.json();
        setAgents(data.agents);
      }
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAgentRuns = useCallback(async (agentId: string) => {
    setRunsLoading(true);
    try {
      const res = await fetch(`/api/runs?agent_id=${agentId}&limit=20`);
      if (res.ok) {
        const data = await res.json();
        setAgentRuns(data.runs);
      }
    } catch {
      setAgentRuns([]);
    } finally {
      setRunsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAgents();
  }, [loadAgents]);

  const toggleExpand = (agentId: string) => {
    if (expandedId === agentId) {
      setExpandedId(null);
      setAgentRuns([]);
    } else {
      setExpandedId(agentId);
      void loadAgentRuns(agentId);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">Agents</h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            {agents.length} agent{agents.length !== 1 ? "s" : ""} in registry
          </p>
        </div>
        <button
          onClick={() => void loadAgents()}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-200 bg-zinc-900 border border-zinc-800 rounded-lg transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Agent cards */}
      {loading && agents.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-zinc-600">
          Loading agents...
        </div>
      ) : agents.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-zinc-600">
          <Bot className="w-8 h-8 mb-2" />
          <p>No agents in registry. Build one via chat.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              expanded={expandedId === agent.id}
              onToggle={() => toggleExpand(agent.id)}
              runs={expandedId === agent.id ? agentRuns : []}
              runsLoading={runsLoading && expandedId === agent.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Components ──────────────────────────────────────────────────────

function AgentCard({
  agent,
  expanded,
  onToggle,
  runs,
  runsLoading,
}: {
  agent: RegistryAgent;
  expanded: boolean;
  onToggle: () => void;
  runs: RunTrace[];
  runsLoading: boolean;
}) {
  const enabledTools: string[] = [];
  if (agent.include_todo) enabledTools.push("todo");
  if (agent.include_filesystem) enabledTools.push("filesystem");
  if (agent.include_subagents) enabledTools.push("subagents");
  if (agent.include_skills) enabledTools.push("skills");
  if (agent.include_memory) enabledTools.push("memory");
  if (agent.include_web) enabledTools.push("web");

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      {/* Header row */}
      <div
        className="flex items-center gap-4 px-4 py-3 cursor-pointer hover:bg-zinc-800/30 transition-colors"
        onClick={onToggle}
      >
        <div className="text-zinc-500">
          {expanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-medium text-zinc-200">{agent.name}</span>
            <RoleBadge role={agent.role} />
          </div>
          <p className="text-xs text-zinc-500 mt-0.5 truncate">{agent.description}</p>
        </div>

        <div className="flex items-center gap-6 text-xs text-zinc-400">
          <span className="flex items-center gap-1">
            <Zap className="w-3 h-3" />
            {agent.total_runs} runs
          </span>
          <span className="flex items-center gap-1">
            <Hash className="w-3 h-3" />
            {agent.total_tokens.toLocaleString()} tokens
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {agent.last_run_at
              ? new Date(agent.last_run_at).toLocaleDateString()
              : "Never"}
          </span>
          <StatusDot status={agent.status} />
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-zinc-800 px-4 py-4 space-y-4">
          {/* Agent info grid */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-xs font-medium text-zinc-500 mb-2">Configuration</h4>
              <div className="space-y-1.5 text-xs">
                <InfoRow label="Role" value={agent.role} />
                <InfoRow label="Status" value={agent.status} />
                <InfoRow
                  label="Token Limit"
                  value={agent.token_limit?.toLocaleString() ?? "Default"}
                />
                <InfoRow
                  label="Cost Budget"
                  value={
                    agent.cost_budget_usd != null
                      ? `$${agent.cost_budget_usd.toFixed(2)}`
                      : "Default"
                  }
                />
                <InfoRow
                  label="Created"
                  value={new Date(agent.created_at).toLocaleString()}
                />
              </div>
            </div>
            <div>
              <h4 className="text-xs font-medium text-zinc-500 mb-2">Enabled Tools</h4>
              {enabledTools.length === 0 ? (
                <p className="text-xs text-zinc-600">No tools enabled</p>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {enabledTools.map((tool) => (
                    <span
                      key={tool}
                      className="px-2 py-0.5 bg-zinc-800 border border-zinc-700 rounded text-xs text-zinc-300"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              )}

              <h4 className="text-xs font-medium text-zinc-500 mt-4 mb-2">
                Instructions
              </h4>
              <pre className="p-2 bg-zinc-950 border border-zinc-800 rounded text-xs text-zinc-400 whitespace-pre-wrap max-h-24 overflow-y-auto">
                {agent.instructions || "(none)"}
              </pre>
            </div>
          </div>

          {/* Run history */}
          <div>
            <h4 className="text-xs font-medium text-zinc-500 mb-2">
              Recent Runs
            </h4>
            {runsLoading ? (
              <p className="text-xs text-zinc-600">Loading runs...</p>
            ) : runs.length === 0 ? (
              <p className="text-xs text-zinc-600">No runs recorded yet.</p>
            ) : (
              <div className="space-y-1">
                {runs.map((run) => (
                  <div
                    key={run.id}
                    className="flex items-center gap-4 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-xs"
                  >
                    <span className="text-zinc-500 w-32 shrink-0">
                      {new Date(run.created_at).toLocaleString("en-US", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                    <span className="text-zinc-300 flex-1 truncate">
                      {run.prompt.slice(0, 80)}
                      {run.prompt.length > 80 ? "..." : ""}
                    </span>
                    <span className="text-zinc-400 tabular-nums">
                      {run.total_tokens.toLocaleString()} tok
                    </span>
                    <span className="text-zinc-400 tabular-nums">
                      {(run.latency_ms / 1000).toFixed(1)}s
                    </span>
                    <SourceBadge source={run.source} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-zinc-500">{label}</span>
      <span className="text-zinc-300">{value}</span>
    </div>
  );
}

function RoleBadge({ role }: { role: string }) {
  const colors: Record<string, string> = {
    worker: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    analysis: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    builder: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  };
  const cls = colors[role] ?? "bg-zinc-800 text-zinc-400 border-zinc-700";
  return (
    <span className={`px-1.5 py-0.5 text-xs rounded border ${cls}`}>{role}</span>
  );
}

function StatusDot({ status }: { status: string }) {
  const color = status === "ready" ? "bg-emerald-400" : "bg-zinc-500";
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      <span className="text-xs text-zinc-400">{status}</span>
    </span>
  );
}

function SourceBadge({ source }: { source: string }) {
  const colors: Record<string, string> = {
    build: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    run: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    cerebro: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    copilot: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  };
  const cls = colors[source] ?? "bg-zinc-800 text-zinc-400 border-zinc-700";
  return (
    <span className={`px-2 py-0.5 text-xs rounded border ${cls}`}>{source}</span>
  );
}
