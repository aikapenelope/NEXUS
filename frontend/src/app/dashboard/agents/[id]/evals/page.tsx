"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  Plus,
  Trash2,
  Play,
  ArrowLeft,
  Check,
  X,
  ChevronDown,
  ChevronUp,
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
import Link from "next/link";
import {
  fetchEvals,
  runEval,
  type EvalRecord,
  type EvalTestCase,
} from "@/lib/api";

// ── Page ────────────────────────────────────────────────────────────

export default function EvalsPage() {
  const params = useParams<{ id: string }>();
  const agentId = params.id;

  const [evals, setEvals] = useState<EvalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [expandedEval, setExpandedEval] = useState<string | null>(null);

  const loadEvals = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchEvals(agentId);
      setEvals(data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    void loadEvals();
  }, [loadEvals]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          href="/dashboard/agents"
          className="text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div className="flex-1">
          <h2 className="text-xl font-semibold text-zinc-100">
            Agent Evaluations
          </h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            {evals.length} evaluation{evals.length !== 1 ? "s" : ""} recorded
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          New Eval
        </button>
      </div>

      {/* New eval form */}
      {showForm && (
        <EvalForm
          agentId={agentId}
          onComplete={() => {
            setShowForm(false);
            void loadEvals();
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {/* Score trend chart */}
      {evals.length > 1 && <ScoreTrend evals={evals} />}

      {/* Eval history */}
      {loading && evals.length === 0 ? (
        <div className="flex items-center justify-center h-32 text-zinc-600">
          Loading evaluations...
        </div>
      ) : evals.length === 0 ? (
        <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-xl text-center">
          <p className="text-sm text-zinc-500">
            No evaluations yet. Click &quot;New Eval&quot; to run your first
            test suite.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {evals.map((ev) => (
            <EvalCard
              key={ev.id}
              eval_={ev}
              expanded={expandedEval === ev.id}
              onToggle={() =>
                setExpandedEval(expandedEval === ev.id ? null : ev.id)
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Eval Form ───────────────────────────────────────────────────────

function EvalForm({
  agentId,
  onComplete,
  onCancel,
}: {
  agentId: string;
  onComplete: () => void;
  onCancel: () => void;
}) {
  const [cases, setCases] = useState<EvalTestCase[]>([
    { prompt: "", expected: "" },
  ]);
  const [evaluator, setEvaluator] = useState("contains");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addCase = () => {
    setCases([...cases, { prompt: "", expected: "" }]);
  };

  const removeCase = (index: number) => {
    setCases(cases.filter((_, i) => i !== index));
  };

  const updateCase = (
    index: number,
    field: "prompt" | "expected",
    value: string
  ) => {
    const updated = [...cases];
    updated[index] = { ...updated[index], [field]: value };
    setCases(updated);
  };

  const handleRun = async () => {
    const valid = cases.filter((c) => c.prompt.trim());
    if (valid.length === 0) {
      setError("Add at least one test case with a prompt");
      return;
    }
    setRunning(true);
    setError(null);
    try {
      await runEval(agentId, valid, evaluator);
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Evaluation failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-zinc-200">
          New Evaluation Suite
        </h3>
        <select
          value={evaluator}
          onChange={(e) => setEvaluator(e.target.value)}
          className="px-2 py-1 text-xs bg-zinc-950 border border-zinc-700 rounded text-zinc-300"
        >
          <option value="contains">Contains</option>
          <option value="exact_match">Exact Match</option>
          <option value="llm_judge">LLM Judge</option>
        </select>
      </div>

      {error && (
        <div className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Test cases */}
      <div className="space-y-2">
        {cases.map((tc, i) => (
          <div
            key={i}
            className="flex gap-2 items-start p-2 bg-zinc-950 border border-zinc-800 rounded-lg"
          >
            <div className="flex-1 space-y-1">
              <input
                type="text"
                value={tc.prompt}
                onChange={(e) => updateCase(i, "prompt", e.target.value)}
                placeholder="Prompt (input to agent)"
                className="w-full px-2 py-1.5 bg-transparent border border-zinc-800 rounded text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
              />
              <input
                type="text"
                value={tc.expected}
                onChange={(e) => updateCase(i, "expected", e.target.value)}
                placeholder="Expected output (or substring)"
                className="w-full px-2 py-1.5 bg-transparent border border-zinc-800 rounded text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
              />
            </div>
            {cases.length > 1 && (
              <button
                onClick={() => removeCase(i)}
                className="p-1 text-zinc-600 hover:text-red-400 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={addCase}
          className="flex items-center gap-1 px-2 py-1 text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-800 border border-zinc-700 rounded transition-colors"
        >
          <Plus className="w-3 h-3" />
          Add Case
        </button>
        <div className="flex-1" />
        <button
          onClick={onCancel}
          disabled={running}
          className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-800 border border-zinc-700 rounded-lg transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={() => void handleRun()}
          disabled={running}
          className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50"
        >
          <Play className="w-3 h-3" />
          {running ? "Running..." : "Run Evaluation"}
        </button>
      </div>
    </div>
  );
}

// ── Eval Card ───────────────────────────────────────────────────────

function EvalCard({
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
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-zinc-200">
              {scores.evaluator} eval
            </span>
            <span
              className={`px-1.5 py-0.5 text-xs rounded ${
                eval_.status === "completed"
                  ? "bg-emerald-500/10 text-emerald-400"
                  : eval_.status === "running"
                    ? "bg-blue-500/10 text-blue-400"
                    : "bg-zinc-800 text-zinc-500"
              }`}
            >
              {eval_.status}
            </span>
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
            <span>{scores.total_cases} cases</span>
            <span>
              Score: {(scores.avg_score * 100).toFixed(0)}%
            </span>
            <span>
              Pass rate: {scores.pass_rate.toFixed(0)}%
            </span>
            <span>
              {new Date(eval_.created_at).toLocaleString()}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ScoreBadge score={scores.avg_score} />
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-zinc-600" />
          ) : (
            <ChevronDown className="w-4 h-4 text-zinc-600" />
          )}
        </div>
      </button>

      {expanded && eval_.results.length > 0 && (
        <div className="border-t border-zinc-800">
          <div className="divide-y divide-zinc-800">
            {eval_.results.map((r, i) => (
              <div key={i} className="px-4 py-2">
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
                <div className="grid grid-cols-1 gap-1 text-xs">
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
                        {r.output.length > 200
                          ? r.output.slice(0, 200) + "..."
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

// ── Score Trend Chart ───────────────────────────────────────────────

function ScoreTrend({ evals }: { evals: EvalRecord[] }) {
  // Reverse to show oldest first
  const chartData = [...evals]
    .reverse()
    .map((ev, i) => ({
      name: `#${i + 1}`,
      score: Math.round(ev.scores.avg_score * 100),
      pass_rate: Math.round(ev.scores.pass_rate),
    }));

  return (
    <div>
      <h3 className="text-sm font-medium text-zinc-400 mb-2">Score Trend</h3>
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis dataKey="name" stroke="#52525b" tick={{ fontSize: 10 }} />
            <YAxis stroke="#52525b" tick={{ fontSize: 10 }} domain={[0, 100]} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#18181b",
                border: "1px solid #3f3f46",
                borderRadius: "8px",
                fontSize: "12px",
              }}
            />
            <Bar dataKey="score" fill="#10b981" name="Avg Score %" radius={[4, 4, 0, 0]} />
            <Bar dataKey="pass_rate" fill="#6366f1" name="Pass Rate %" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
