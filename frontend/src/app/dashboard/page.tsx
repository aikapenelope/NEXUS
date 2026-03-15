"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  Bot,
  Zap,
  Hash,
  Clock,
  RefreshCw,
} from "lucide-react";

// ── Types ───────────────────────────────────────────────────────────

interface DashboardStats {
  total_agents: number;
  total_runs: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  avg_latency_ms: number;
  runs_per_day: { day: string; runs: number; tokens: number }[];
  top_agents: {
    agent_name: string;
    runs: number;
    tokens: number;
    avg_latency: number;
  }[];
  source_breakdown: { source: string; runs: number; tokens: number }[];
  model_breakdown: { model: string; runs: number; tokens: number }[];
}

const COLORS = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

// ── Page ────────────────────────────────────────────────────────────

export default function DashboardOverview() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/dashboard");
      if (res.ok) {
        const data = await res.json();
        setStats(data.stats);
      }
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-500">
        Loading dashboard...
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-500">
        Failed to load dashboard data.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">Overview</h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            Platform metrics and usage analytics
          </p>
        </div>
        <button
          onClick={() => void load()}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-200 bg-zinc-900 border border-zinc-800 rounded-lg transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <KpiCard
          icon={<Bot className="w-5 h-5" />}
          label="Total Agents"
          value={stats.total_agents.toString()}
          color="text-emerald-400"
        />
        <KpiCard
          icon={<Zap className="w-5 h-5" />}
          label="Total Runs"
          value={stats.total_runs.toLocaleString()}
          color="text-blue-400"
        />
        <KpiCard
          icon={<Hash className="w-5 h-5" />}
          label="Total Tokens"
          value={formatTokens(stats.total_tokens)}
          subtitle={`${formatTokens(stats.total_input_tokens)} in / ${formatTokens(stats.total_output_tokens)} out`}
          color="text-amber-400"
        />
        <KpiCard
          icon={<Clock className="w-5 h-5" />}
          label="Avg Latency"
          value={`${(stats.avg_latency_ms / 1000).toFixed(1)}s`}
          color="text-purple-400"
        />
      </div>

      {/* Charts row 1: Time series */}
      <div className="grid grid-cols-2 gap-4">
        <ChartCard title="Runs per Day (7d)">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stats.runs_per_day}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="day"
                tickFormatter={(v: string) => v.slice(5)}
                stroke="#52525b"
                fontSize={12}
              />
              <YAxis stroke="#52525b" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #27272a",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                labelFormatter={(v) => String(v)}
              />
              <Bar dataKey="runs" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Tokens per Day (7d)">
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={stats.runs_per_day}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="day"
                tickFormatter={(v: string) => v.slice(5)}
                stroke="#52525b"
                fontSize={12}
              />
              <YAxis stroke="#52525b" fontSize={12} tickFormatter={formatTokens} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #27272a",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                labelFormatter={(v) => String(v)}
                formatter={(value) => [formatTokens(Number(value)), "Tokens"]}
              />
              <Area
                type="monotone"
                dataKey="tokens"
                stroke="#10b981"
                fill="#10b981"
                fillOpacity={0.15}
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Charts row 2: Breakdowns */}
      <div className="grid grid-cols-3 gap-4">
        {/* Top Agents */}
        <ChartCard title="Top Agents">
          {stats.top_agents.length === 0 ? (
            <EmptyState text="No agent runs yet" />
          ) : (
            <div className="space-y-2">
              {stats.top_agents.slice(0, 5).map((a, i) => (
                <div key={a.agent_name} className="flex items-center gap-3">
                  <span className="text-xs text-zinc-500 w-4">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-zinc-200 truncate">{a.agent_name}</div>
                    <div className="text-xs text-zinc-500">
                      {a.runs} runs &middot; {formatTokens(a.tokens)} tokens
                    </div>
                  </div>
                  <div className="text-xs text-zinc-400">{(a.avg_latency / 1000).toFixed(1)}s</div>
                </div>
              ))}
            </div>
          )}
        </ChartCard>

        {/* Source Breakdown */}
        <ChartCard title="By Source">
          {stats.source_breakdown.length === 0 ? (
            <EmptyState text="No runs yet" />
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={stats.source_breakdown}
                  dataKey="runs"
                  nameKey="source"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  label={({ name, value }: { name?: string; value?: number }) =>
                    `${name ?? ""} (${value ?? 0})`
                  }
                  labelLine={false}
                  fontSize={11}
                >
                  {stats.source_breakdown.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #27272a",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Model Breakdown */}
        <ChartCard title="By Model">
          {stats.model_breakdown.length === 0 ? (
            <EmptyState text="No runs yet" />
          ) : (
            <div className="space-y-2">
              {stats.model_breakdown.map((m, i) => (
                <div key={m.model} className="flex items-center gap-3">
                  <div
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: COLORS[i % COLORS.length] }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-zinc-200 truncate">{m.model}</div>
                    <div className="text-xs text-zinc-500">
                      {m.runs} runs &middot; {formatTokens(m.tokens)} tokens
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ChartCard>
      </div>
    </div>
  );
}

// ── Components ──────────────────────────────────────────────────────

function KpiCard({
  icon,
  label,
  value,
  subtitle,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  subtitle?: string;
  color: string;
}) {
  return (
    <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-xl">
      <div className={`${color} mb-2`}>{icon}</div>
      <div className="text-2xl font-semibold text-zinc-100">{value}</div>
      <div className="text-xs text-zinc-500 mt-0.5">{label}</div>
      {subtitle && <div className="text-xs text-zinc-600 mt-0.5">{subtitle}</div>}
    </div>
  );
}

function ChartCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-xl">
      <h3 className="text-sm font-medium text-zinc-300 mb-3">{title}</h3>
      {children}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center h-32 text-zinc-600 text-sm">
      {text}
    </div>
  );
}

// ── Helpers ─────────────────────────────────────────────────────────

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}
