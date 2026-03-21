// @ts-nocheck — legacy evals page, needs rewrite to match new eval suite
"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  FlaskConical,
  RefreshCw,
  Check,
  X,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  Target,
  BarChart3,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  fetchEvals as fetchAllEvals,
  type EvalRecord,
} from "@/lib/api";

// ── Page ────────────────────────────────────────────────────────────

export default function EvalsPage() {
  const [evals, setEvals] = useState<EvalRecord[]>([]);
  const [summary, setSummary] = useState<EvalsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filterAgent, setFilterAgent] = useState<string>("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [evalsData, summaryData] = await Promise.all([
        fetchAllEvals({
          limit: 100,
          agentId: filterAgent || undefined,
        }),
        fetchEvalsSummary(),
      ]);
      setEvals(evalsData);
      setSummary(summaryData);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [filterAgent]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // Unique agents for filter dropdown
  const agentOptions = summary?.agents ?? [];

  // Global avg score
  const globalAvgScore =
    evals.length > 0
      ? evals.reduce((sum, e) => sum + (e.scores?.avg_score ?? 0), 0) /
        evals.length
      : 0;
  const globalPassRate =
    evals.length > 0
      ? evals.reduce((sum, e) => sum + (e.scores?.pass_rate ?? 0), 0) /
        evals.length
      : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100 flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-emerald-400" />
            Evaluations
          </h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            Agent evaluation runs and quality metrics
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Agent filter */}
          <select
            value={filterAgent}
            onChange={(e) => setFilterAgent(e.target.value)}
            className="px-2 py-1.5 text-xs bg-zinc-900 border border-zinc-700 rounded-lg text-zinc-300"
          >
            <option value="">All Agents</option>
            {agentOptions.map((a) => (
              <option key={a.agent_id} value={a.agent_id}>
                {a.agent_name}
              </option>
            ))}
          </select>
          <button
            onClick={() => void loadData()}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-200 bg-zinc-900 border border-zinc-800 rounded-lg transition-colors"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-4 gap-4">
          <SummaryCard
            label="Total Evals"
            value={String(summary.total_evals)}
            icon={<FlaskConical className="w-4 h-4 text-indigo-400" />}
            color="indigo"
          />
          <SummaryCard
            label="Completed"
            value={String(summary.completed)}
            icon={<Check className="w-4 h-4 text-emerald-400" />}
            color="emerald"
          />
          <SummaryCard
            label="Avg Score"
            value={`${(globalAvgScore * 100).toFixed(0)}%`}
            icon={<TrendingUp className="w-4 h-4 text-amber-400" />}
            color="amber"
          />
          <SummaryCard
            label="Avg Pass Rate"
            value={`${globalPassRate.toFixed(0)}%`}
            icon={<Target className="w-4 h-4 text-blue-400" />}
            color="blue"
          />
        </div>
      )}

      {/* Per-agent breakdown */}
      {summary && summary.agents.length > 0 && (
        <AgentBreakdown agents={summary.agents} />
      )}

      {/* Score trend chart */}
      {evals.length > 1 && <GlobalScoreTrend evals={evals} />}

      {/* Eval runs table */}
      <div>
        <h3 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
          <BarChart3 className="w-4 h-4" />
          Evaluation Runs ({evals.length})
        </h3>

        {loading && evals.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-zinc-600">
            Loading evaluations...
          </div>
        ) : evals.length === 0 ? (
          <div className="p-8 bg-zinc-900 border border-zinc-800 rounded-xl text-center">
            <FlaskConical className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
            <p className="text-sm text-zinc-500">
              No evaluations yet. Go to an agent&apos;s page and run your first
              eval.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {evals.map((ev) => (
              <EvalRow
                key={ev.id}
                eval_={ev}
                expanded={expandedId === ev.id}
                onToggle={() =>
                  setExpandedId(expandedId === ev.id ? null : ev.id)
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Summary Card ────────────────────────────────────────────────────

function SummaryCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color: string;
}) {
  const borderColors: Record<string, string> = {
    indigo: "border-indigo-500/20",
    emerald: "border-emerald-500/20",
    amber: "border-amber-500/20",
    blue: "border-blue-500/20",
  };
  return (
    <div
      className={`bg-zinc-900 border ${borderColors[color] ?? "border-zinc-800"} rounded-xl p-4`}
    >
      <div className="flex items-center gap-2 mb-2">{icon}</div>
      <div className="text-2xl font-semibold text-zinc-100">{value}</div>
      <div className="text-xs text-zinc-500 mt-0.5">{label}</div>
    </div>
  );
}

// ── Agent Breakdown ─────────────────────────────────────────────────

function AgentBreakdown({
  agents,
}: {
  agents: {
    agent_id: string;
    agent_name: string;
    eval_count: number;
    avg_score: number;
    avg_pass_rate: number;
    last_eval_at: string | null;
  }[];
}) {
  return (
    <div>
      <h3 className="text-sm font-medium text-zinc-400 mb-3">
        Per-Agent Summary
      </h3>
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500">
              <th className="text-left px-4 py-2 font-medium">Agent</th>
              <th className="text-right px-4 py-2 font-medium">Evals</th>
              <th className="text-right px-4 py-2 font-medium">Avg Score</th>
              <th className="text-right px-4 py-2 font-medium">Pass Rate</th>
              <th className="text-right px-4 py-2 font-medium">Last Eval</th>
              <th className="text-right px-4 py-2 font-medium" />
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => (
              <tr
                key={a.agent_id}
                className="border-b border-zinc-800/50 hover:bg-zinc-800/30"
              >
                <td className="px-4 py-2 text-zinc-200 font-medium">
                  {a.agent_name}
                </td>
                <td className="px-4 py-2 text-right text-zinc-400">
                  {a.eval_count}
                </td>
                <td className="px-4 py-2 text-right">
                  <ScoreBadge score={a.avg_score} />
                </td>
                <td className="px-4 py-2 text-right text-zinc-400">
                  {a.avg_pass_rate.toFixed(0)}%
                </td>
                <td className="px-4 py-2 text-right text-zinc-500">
                  {a.last_eval_at
                    ? new Date(a.last_eval_at).toLocaleDateString()
                    : "-"}
                </td>
                <td className="px-4 py-2 text-right">
                  <Link
                    href={`/dashboard/agents/${a.agent_id}/evals`}
                    className="text-emerald-400 hover:text-emerald-300 transition-colors"
                  >
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Eval Row ────────────────────────────────────────────────────────

function EvalRow({
  eval_,
  expanded,
  onToggle,
}: {
  eval_: EvalRecord;
  expanded: boolean;
  onToggle: () => void;
}) {
  const scores = eval_.scores;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-4 px-4 py-3 text-left hover:bg-zinc-800/30 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-zinc-200">
              {eval_.agent_name}
            </span>
            <span className="px-1.5 py-0.5 text-xs rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
              {scores.evaluator}
            </span>
            <StatusBadge status={eval_.status} />
          </div>
          <div className="flex items-center gap-4 mt-1 text-xs text-zinc-500">
            <span>{scores.total_cases} cases</span>
            <span>
              {scores.passed} passed / {scores.failed} failed
            </span>
            <span>{new Date(eval_.created_at).toLocaleString()}</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-xs text-zinc-500">Score</div>
            <ScoreBadge score={scores.avg_score} />
          </div>
          <div className="text-right">
            <div className="text-xs text-zinc-500">Pass</div>
            <span className="text-xs text-zinc-300">
              {scores.pass_rate.toFixed(0)}%
            </span>
          </div>
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-zinc-600" />
          ) : (
            <ChevronDown className="w-4 h-4 text-zinc-600" />
          )}
        </div>
      </button>

      {expanded && eval_.results.length > 0 && (
        <div className="border-t border-zinc-800">
          <div className="divide-y divide-zinc-800/50">
            {eval_.results.map((r, i) => (
              <div key={i} className="px-4 py-2.5">
                <div className="flex items-center gap-2 mb-1">
                  {r.score >= 0.5 ? (
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <X className="w-3.5 h-3.5 text-red-400" />
                  )}
                  <span className="text-xs font-medium text-zinc-300">
                    Case {i + 1}
                  </span>
                  <span className="text-xs text-zinc-500">
                    Score: {(r.score * 100).toFixed(0)}%
                  </span>
                  {r.error && (
                    <span className="text-xs text-red-400">{r.error}</span>
                  )}
                </div>
                <div className="grid grid-cols-1 gap-1 text-xs pl-5">
                  <div>
                    <span className="text-zinc-600">Prompt: </span>
                    <span className="text-zinc-400">{r.prompt}</span>
                  </div>
                  <div>
                    <span className="text-zinc-600">Expected: </span>
                    <span className="text-zinc-400">{r.expected}</span>
                  </div>
                  {r.output && (
                    <div>
                      <span className="text-zinc-600">Output: </span>
                      <span className="text-zinc-400 break-all">
                        {r.output.length > 300
                          ? r.output.slice(0, 300) + "..."
                          : r.output}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Score Badge ──────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80
      ? "bg-emerald-500/10 text-emerald-400"
      : pct >= 50
        ? "bg-amber-500/10 text-amber-400"
        : "bg-red-500/10 text-red-400";

  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded ${color}`}>
      {pct}%
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "completed"
      ? "bg-emerald-500/10 text-emerald-400"
      : status === "running"
        ? "bg-blue-500/10 text-blue-400 animate-pulse"
        : "bg-zinc-800 text-zinc-500";
  return (
    <span className={`px-1.5 py-0.5 text-xs rounded ${color}`}>{status}</span>
  );
}

// ── Global Score Trend ──────────────────────────────────────────────

function GlobalScoreTrend({ evals }: { evals: EvalRecord[] }) {
  const chartData = [...evals]
    .reverse()
    .map((ev, i) => ({
      name: `#${i + 1}`,
      agent: ev.agent_name,
      score: Math.round(ev.scores.avg_score * 100),
      pass_rate: Math.round(ev.scores.pass_rate),
    }));

  return (
    <div>
      <h3 className="text-sm font-medium text-zinc-400 mb-2">
        Score Trend (All Agents)
      </h3>
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis dataKey="name" stroke="#52525b" tick={{ fontSize: 10 }} />
            <YAxis
              stroke="#52525b"
              tick={{ fontSize: 10 }}
              domain={[0, 100]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#18181b",
                border: "1px solid #3f3f46",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              labelFormatter={(_, payload) => {
                const item = payload?.[0]?.payload as
                  | { agent?: string }
                  | undefined;
                return item?.agent ?? "";
              }}
            />
            <Bar
              dataKey="score"
              fill="#10b981"
              name="Avg Score %"
              radius={[4, 4, 0, 0]}
            />
            <Bar
              dataKey="pass_rate"
              fill="#6366f1"
              name="Pass Rate %"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
