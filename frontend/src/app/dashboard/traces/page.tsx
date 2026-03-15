"use client";

import { useEffect, useState, useCallback } from "react";
import {
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Clock,
  Hash,
  CheckCircle2,
  XCircle,
} from "lucide-react";

// ── Types ───────────────────────────────────────────────────────────

interface RunTrace {
  id: string;
  agent_id: string | null;
  agent_name: string;
  prompt: string;
  output: string;
  model: string;
  role: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  status: string;
  source: string;
  created_at: string;
}

type SortField = "created_at" | "agent_name" | "total_tokens" | "latency_ms";
type SortDir = "asc" | "desc";

// ── Page ────────────────────────────────────────────────────────────

export default function TracesPage() {
  const [runs, setRuns] = useState<RunTrace[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [sourceFilter, setSourceFilter] = useState<string>("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (sourceFilter !== "all") params.set("source", sourceFilter);
      const res = await fetch(`/api/runs?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setRuns(data.runs);
      }
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [sourceFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const sorted = [...runs].sort((a, b) => {
    const aVal = a[sortField];
    const bVal = b[sortField];
    if (typeof aVal === "string" && typeof bVal === "string") {
      return sortDir === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    }
    return sortDir === "asc"
      ? (aVal as number) - (bVal as number)
      : (bVal as number) - (aVal as number);
  });

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">Traces</h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            {runs.length} run{runs.length !== 1 ? "s" : ""} logged
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Source filter */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="px-3 py-1.5 text-sm bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-300 focus:outline-none focus:border-zinc-600"
          >
            <option value="all">All sources</option>
            <option value="build">Build</option>
            <option value="run">Run</option>
            <option value="cerebro">Cerebro</option>
            <option value="copilot">Copilot</option>
          </select>
          <button
            onClick={() => void load()}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-200 bg-zinc-900 border border-zinc-800 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800">
              <th className="w-8 px-3 py-3" />
              <SortHeader
                label="Timestamp"
                field="created_at"
                current={sortField}
                dir={sortDir}
                onSort={toggleSort}
              />
              <SortHeader
                label="Agent"
                field="agent_name"
                current={sortField}
                dir={sortDir}
                onSort={toggleSort}
              />
              <th className="px-3 py-3 text-left text-zinc-500 font-medium">Model</th>
              <th className="px-3 py-3 text-left text-zinc-500 font-medium">Source</th>
              <SortHeader
                label="Tokens"
                field="total_tokens"
                current={sortField}
                dir={sortDir}
                onSort={toggleSort}
              />
              <SortHeader
                label="Latency"
                field="latency_ms"
                current={sortField}
                dir={sortDir}
                onSort={toggleSort}
              />
              <th className="px-3 py-3 text-left text-zinc-500 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && runs.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-12 text-center text-zinc-600">
                  Loading traces...
                </td>
              </tr>
            ) : sorted.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-12 text-center text-zinc-600">
                  No traces found. Run an agent to see traces here.
                </td>
              </tr>
            ) : (
              sorted.map((run) => (
                <TraceRow
                  key={run.id}
                  run={run}
                  expanded={expandedId === run.id}
                  onToggle={() =>
                    setExpandedId(expandedId === run.id ? null : run.id)
                  }
                />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Components ──────────────────────────────────────────────────────

function SortHeader({
  label,
  field,
  current,
  dir,
  onSort,
}: {
  label: string;
  field: SortField;
  current: SortField;
  dir: SortDir;
  onSort: (f: SortField) => void;
}) {
  const isActive = current === field;
  return (
    <th
      className="px-3 py-3 text-left text-zinc-500 font-medium cursor-pointer hover:text-zinc-300 select-none"
      onClick={() => onSort(field)}
    >
      <span className="flex items-center gap-1">
        {label}
        {isActive && (
          <span className="text-xs">{dir === "asc" ? "\u2191" : "\u2193"}</span>
        )}
      </span>
    </th>
  );
}

function TraceRow({
  run,
  expanded,
  onToggle,
}: {
  run: RunTrace;
  expanded: boolean;
  onToggle: () => void;
}) {
  const date = new Date(run.created_at);
  const timeStr = date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <>
      <tr
        className="border-b border-zinc-800/50 hover:bg-zinc-800/30 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <td className="px-3 py-2.5 text-zinc-500">
          {expanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </td>
        <td className="px-3 py-2.5 text-zinc-400 text-xs whitespace-nowrap">
          {timeStr}
        </td>
        <td className="px-3 py-2.5 text-zinc-200">{run.agent_name}</td>
        <td className="px-3 py-2.5 text-zinc-400 text-xs">{run.model || "-"}</td>
        <td className="px-3 py-2.5">
          <SourceBadge source={run.source} />
        </td>
        <td className="px-3 py-2.5 text-zinc-300 tabular-nums">
          <span className="flex items-center gap-1">
            <Hash className="w-3 h-3 text-zinc-600" />
            {run.total_tokens.toLocaleString()}
          </span>
        </td>
        <td className="px-3 py-2.5 text-zinc-300 tabular-nums">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-zinc-600" />
            {(run.latency_ms / 1000).toFixed(1)}s
          </span>
        </td>
        <td className="px-3 py-2.5">
          {run.status === "completed" ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          ) : (
            <XCircle className="w-4 h-4 text-red-400" />
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-zinc-800/50">
          <td colSpan={8} className="px-6 py-4 bg-zinc-950/50">
            <TraceDetail run={run} />
          </td>
        </tr>
      )}
    </>
  );
}

function TraceDetail({ run }: { run: RunTrace }) {
  return (
    <div className="space-y-4">
      {/* Token breakdown */}
      <div className="grid grid-cols-4 gap-4">
        <MiniStat label="Input Tokens" value={run.input_tokens.toLocaleString()} />
        <MiniStat label="Output Tokens" value={run.output_tokens.toLocaleString()} />
        <MiniStat label="Total Tokens" value={run.total_tokens.toLocaleString()} />
        <MiniStat label="Latency" value={`${(run.latency_ms / 1000).toFixed(2)}s`} />
      </div>

      {/* Prompt */}
      <div>
        <h4 className="text-xs font-medium text-zinc-500 mb-1">Prompt</h4>
        <pre className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-zinc-300 whitespace-pre-wrap max-h-40 overflow-y-auto">
          {run.prompt || "(empty)"}
        </pre>
      </div>

      {/* Output */}
      <div>
        <h4 className="text-xs font-medium text-zinc-500 mb-1">Output</h4>
        <pre className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-zinc-300 whitespace-pre-wrap max-h-60 overflow-y-auto">
          {run.output || "(empty)"}
        </pre>
      </div>

      {/* Metadata */}
      <div className="flex gap-4 text-xs text-zinc-500">
        <span>ID: {run.id}</span>
        {run.agent_id && <span>Agent ID: {run.agent_id}</span>}
        <span>Role: {run.role}</span>
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-2 bg-zinc-900 border border-zinc-800 rounded-lg">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="text-sm font-medium text-zinc-200 mt-0.5">{value}</div>
    </div>
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
    <span className={`px-2 py-0.5 text-xs rounded border ${cls}`}>
      {source}
    </span>
  );
}
