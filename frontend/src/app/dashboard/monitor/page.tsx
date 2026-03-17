"use client";

import { useEffect, useState, useCallback } from "react";
import {
  RefreshCw,
  Bot,
  Zap,
  AlertTriangle,
  Clock,
  Hash,
  ChevronDown,
  ChevronUp,
  X,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  fetchMonitorData,
  type MonitorData,
  type RunInfo,
} from "@/lib/api";

// ── Event type colors ───────────────────────────────────────────────

const EVENT_COLORS: Record<string, string> = {
  agent_start: "text-blue-400",
  agent_complete: "text-emerald-400",
  agent_error: "text-red-400",
  workflow_start: "text-violet-400",
  workflow_complete: "text-emerald-400",
  workflow_error: "text-red-400",
  tool_call: "text-amber-400",
  approval_requested: "text-yellow-400",
  approval_granted: "text-emerald-400",
  approval_rejected: "text-red-400",
};

// ── Page ────────────────────────────────────────────────────────────

export default function MonitorPage() {
  const [data, setData] = useState<MonitorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selectedRun, setSelectedRun] = useState<RunInfo | null>(null);

  const loadData = useCallback(async () => {
    try {
      const result = await fetchMonitorData();
      setData(result);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // Auto-refresh every 10s
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => void loadData(), 10_000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadData]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-600">
        Loading monitor data...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-600">
        No data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">Monitor</h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            Real-time agent monitoring and metrics
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
              autoRefresh
                ? "bg-emerald-600/20 text-emerald-400 border-emerald-500/30"
                : "bg-zinc-900 text-zinc-500 border-zinc-800"
            }`}
          >
            {autoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
          </button>
          <button
            onClick={() => void loadData()}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-200 bg-zinc-900 border border-zinc-800 rounded-lg transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Agent Status Grid */}
      <div>
        <h3 className="text-sm font-medium text-zinc-400 mb-2">
          Agent Status
        </h3>
        {data.agent_status.length === 0 ? (
          <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-xl text-sm text-zinc-600">
            No agent activity yet
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.agent_status.map((agent) => (
              <div
                key={agent.agent_name}
                className={`p-4 rounded-xl border transition-colors ${
                  agent.status === "error"
                    ? "bg-zinc-900 border-red-500/20"
                    : "bg-zinc-900 border-zinc-800"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Bot className="w-4 h-4 text-zinc-500" />
                  <span className="text-sm font-medium text-zinc-200 truncate">
                    {agent.agent_name}
                  </span>
                  <span
                    className={`ml-auto px-1.5 py-0.5 text-xs rounded ${
                      agent.status === "error"
                        ? "bg-red-500/10 text-red-400"
                        : "bg-emerald-500/10 text-emerald-400"
                    }`}
                  >
                    {agent.status === "error" ? "Has Errors" : "Healthy"}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="flex items-center gap-1 text-zinc-500">
                    <Hash className="w-3 h-3" />
                    {agent.total_runs} runs
                  </div>
                  <div className="flex items-center gap-1 text-zinc-500">
                    <Zap className="w-3 h-3" />
                    {agent.total_tokens.toLocaleString()} tok
                  </div>
                  <div className="flex items-center gap-1 text-zinc-500">
                    <Clock className="w-3 h-3" />
                    {agent.avg_latency_ms}ms avg
                  </div>
                  {agent.error_count > 0 && (
                    <div className="flex items-center gap-1 text-red-400">
                      <AlertTriangle className="w-3 h-3" />
                      {agent.error_count} errors
                    </div>
                  )}
                </div>
                {agent.last_run_at && (
                  <div className="mt-2 text-xs text-zinc-600">
                    Last run:{" "}
                    {new Date(agent.last_run_at).toLocaleString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Metrics Charts */}
      {data.latency_series.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-zinc-400 mb-2">
            Latency (24h)
          </h3>
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={data.latency_series}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey="hour"
                  stroke="#52525b"
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v: string) =>
                    v ? new Date(v).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""
                  }
                />
                <YAxis stroke="#52525b" tick={{ fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #3f3f46",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                  labelFormatter={(v) =>
                    typeof v === "string" && v ? new Date(v).toLocaleString() : ""
                  }
                />
                <Legend wrapperStyle={{ fontSize: "11px" }} />
                <Line
                  type="monotone"
                  dataKey="p50"
                  stroke="#10b981"
                  name="p50"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="p95"
                  stroke="#f59e0b"
                  name="p95"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="avg_latency"
                  stroke="#6366f1"
                  name="avg"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Two-column: Live Activity Feed + Recent Runs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Live Activity Feed */}
        <div>
          <h3 className="text-sm font-medium text-zinc-400 mb-2">
            Live Activity Feed
          </h3>
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl max-h-[400px] overflow-y-auto">
            {data.recent_events.length === 0 ? (
              <div className="p-4 text-sm text-zinc-600">No events yet</div>
            ) : (
              <div className="divide-y divide-zinc-800">
                {data.recent_events.map((event) => (
                  <div key={event.id} className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-mono ${
                          EVENT_COLORS[event.event_type] ?? "text-zinc-500"
                        }`}
                      >
                        {event.event_type}
                      </span>
                      <span className="text-xs text-zinc-500 truncate">
                        {event.agent_name}
                      </span>
                      <span className="ml-auto text-xs text-zinc-600">
                        {new Date(event.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    {event.detail && (
                      <p className="text-xs text-zinc-600 mt-0.5 truncate">
                        {event.detail}
                      </p>
                    )}
                    <div className="flex items-center gap-3 mt-0.5 text-xs text-zinc-700">
                      {event.tokens > 0 && <span>{event.tokens} tok</span>}
                      {event.latency_ms > 0 && (
                        <span>{event.latency_ms}ms</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Recent Runs */}
        <div>
          <h3 className="text-sm font-medium text-zinc-400 mb-2">
            Recent Runs
          </h3>
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl max-h-[400px] overflow-y-auto">
            {data.recent_runs.length === 0 ? (
              <div className="p-4 text-sm text-zinc-600">No runs yet</div>
            ) : (
              <div className="divide-y divide-zinc-800">
                {data.recent_runs.map((run) => (
                  <button
                    key={run.id}
                    onClick={() =>
                      setSelectedRun(
                        selectedRun?.id === run.id ? null : run
                      )
                    }
                    className="w-full text-left px-3 py-2 hover:bg-zinc-800/50 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-zinc-300 truncate">
                        {run.agent_name}
                      </span>
                      <span
                        className={`px-1.5 py-0.5 text-xs rounded ${
                          run.status === "error"
                            ? "bg-red-500/10 text-red-400"
                            : "bg-emerald-500/10 text-emerald-400"
                        }`}
                      >
                        {run.status}
                      </span>
                      <span className="ml-auto text-xs text-zinc-600">
                        {run.latency_ms}ms
                      </span>
                      {selectedRun?.id === run.id ? (
                        <ChevronUp className="w-3 h-3 text-zinc-600" />
                      ) : (
                        <ChevronDown className="w-3 h-3 text-zinc-600" />
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-0.5 text-xs text-zinc-600">
                      <span>{run.source}</span>
                      <span>{run.model || "unknown"}</span>
                      <span>{run.total_tokens} tok</span>
                      <span className="ml-auto">
                        {new Date(run.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Run Inspector Modal */}
      {selectedRun && (
        <RunInspector run={selectedRun} onClose={() => setSelectedRun(null)} />
      )}
    </div>
  );
}

// ── Run Inspector ───────────────────────────────────────────────────

function RunInspector({
  run,
  onClose,
}: {
  run: RunInfo;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-2xl max-h-[80vh] bg-zinc-900 border border-zinc-700 rounded-xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800">
          <div>
            <h3 className="text-sm font-medium text-zinc-200">
              Run Inspector
            </h3>
            <p className="text-xs text-zinc-500 mt-0.5">
              {run.agent_name} - {run.source} -{" "}
              {new Date(run.created_at).toLocaleString()}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Metrics row */}
          <div className="grid grid-cols-4 gap-3">
            <MetricBox label="Status" value={run.status} />
            <MetricBox label="Latency" value={`${run.latency_ms}ms`} />
            <MetricBox label="Tokens" value={run.total_tokens.toString()} />
            <MetricBox label="Model" value={run.model || "N/A"} />
          </div>

          {/* Token breakdown */}
          <div className="grid grid-cols-2 gap-3">
            <MetricBox
              label="Input Tokens"
              value={run.input_tokens.toString()}
            />
            <MetricBox
              label="Output Tokens"
              value={run.output_tokens.toString()}
            />
          </div>

          {/* Prompt */}
          <div>
            <h4 className="text-xs font-medium text-zinc-500 mb-1">Prompt</h4>
            <pre className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-zinc-300 whitespace-pre-wrap max-h-40 overflow-y-auto">
              {run.prompt || "(empty)"}
            </pre>
          </div>

          {/* Output */}
          <div>
            <h4 className="text-xs font-medium text-zinc-500 mb-1">Output</h4>
            <pre className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-zinc-300 whitespace-pre-wrap max-h-60 overflow-y-auto">
              {run.output || "(empty)"}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-2 bg-zinc-950 border border-zinc-800 rounded-lg">
      <div className="text-xs text-zinc-600">{label}</div>
      <div className="text-sm font-medium text-zinc-300 mt-0.5 truncate">
        {value}
      </div>
    </div>
  );
}
