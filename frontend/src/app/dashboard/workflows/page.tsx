"use client";

import { useEffect, useState, useCallback } from "react";
import {
  RefreshCw,
  ChevronDown,
  ChevronRight,
  GitBranch,
  Clock,
  Zap,
  Trash2,
  X,
  Check,
  Plus,
  Play,
  Loader2,
} from "lucide-react";
import {
  fetchWorkflows,
  createWorkflow,
  deleteWorkflow,
  runWorkflow,
  approveWorkflow,
  rejectWorkflow,
  fetchAgents,
} from "@/lib/api";
import type {
  Workflow,
  CreateWorkflowPayload,
  WorkflowStep,
  WorkflowRunResult,
} from "@/lib/api";
import type { RegistryAgent } from "@/lib/types";
import { WorkflowCanvas } from "@/components/workflow/WorkflowCanvas";

// ── Page ────────────────────────────────────────────────────────────

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [agents, setAgents] = useState<RegistryAgent[]>([]);

  const loadWorkflows = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchWorkflows();
      setWorkflows(data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAgents = useCallback(async () => {
    try {
      const data = await fetchAgents();
      setAgents(data);
    } catch {
      // silently fail
    }
  }, []);

  useEffect(() => {
    void loadWorkflows();
    void loadAgents();
  }, [loadWorkflows, loadAgents]);

  const handleCreate = async (payload: CreateWorkflowPayload) => {
    const newWorkflow = await createWorkflow(payload);
    setWorkflows((prev) => [newWorkflow, ...prev]);
    setShowCreate(false);
  };

  const handleDelete = async (workflowId: string) => {
    await deleteWorkflow(workflowId);
    setWorkflows((prev) => prev.filter((w) => w.id !== workflowId));
    if (expandedId === workflowId) {
      setExpandedId(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">Workflows</h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            {workflows.length} workflow{workflows.length !== 1 ? "s" : ""}{" "}
            defined
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            New Workflow
          </button>
          <button
            onClick={() => void loadWorkflows()}
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

      {/* Create form */}
      {showCreate && (
        <CreateWorkflowForm
          agents={agents}
          onCreate={handleCreate}
          onCancel={() => setShowCreate(false)}
        />
      )}

      {/* Workflow cards */}
      {loading && workflows.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-zinc-600">
          Loading workflows...
        </div>
      ) : workflows.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-zinc-600">
          <GitBranch className="w-8 h-8 mb-2" />
          <p>No workflows defined yet. Create one to chain agents.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {workflows.map((workflow) => (
            <WorkflowCard
              key={workflow.id}
              workflow={workflow}
              expanded={expandedId === workflow.id}
              onToggle={() =>
                setExpandedId(
                  expandedId === workflow.id ? null : workflow.id
                )
              }
              onDelete={handleDelete}
              onRunComplete={() => void loadWorkflows()}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Create Workflow Form ────────────────────────────────────────────

function CreateWorkflowForm({
  agents,
  onCreate,
  onCancel,
}: {
  agents: RegistryAgent[];
  onCreate: (payload: CreateWorkflowPayload) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [steps, setSteps] = useState<WorkflowStep[]>([
    { agent_name: "", prompt_template: "{input}", requires_approval: false },
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"form" | "visual">("form");

  const addStep = () => {
    setSteps((prev) => [
      ...prev,
      { agent_name: "", prompt_template: "{input}", requires_approval: false },
    ]);
  };

  const removeStep = (index: number) => {
    if (steps.length <= 1) return;
    setSteps((prev) => prev.filter((_, i) => i !== index));
  };

  const updateStep = (
    index: number,
    field: keyof WorkflowStep,
    value: string | boolean
  ) => {
    setSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...s, [field]: value } : s))
    );
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    const validSteps = steps.filter((s) => s.agent_name.trim());
    if (validSteps.length === 0) {
      setError("At least one step with an agent is required");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await onCreate({
        name: name.trim(),
        description: description.trim(),
        steps: validSteps,
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create workflow"
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-zinc-900 border border-emerald-500/30 rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-zinc-200 flex items-center gap-2">
          <Plus className="w-4 h-4 text-emerald-400" />
          Create New Workflow
        </h3>
        <div className="flex items-center gap-1 bg-zinc-950 rounded-lg p-0.5 border border-zinc-800">
          <button
            onClick={() => setMode("form")}
            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
              mode === "form"
                ? "bg-zinc-800 text-zinc-200"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Form
          </button>
          <button
            onClick={() => setMode("visual")}
            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
              mode === "visual"
                ? "bg-zinc-800 text-zinc-200"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Visual
          </button>
        </div>
      </div>

      {error && (
        <div className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <FormField label="Name">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="research-and-summarize"
            className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-700 rounded text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
          />
        </FormField>
        <FormField label="Description">
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What does this workflow do?"
            className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-700 rounded text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
          />
        </FormField>
      </div>

      {/* Visual mode */}
      {mode === "visual" && (
        <div className="h-[400px]">
          <WorkflowCanvas
            agents={agents}
            initialSteps={
              steps.some((s) => s.agent_name) ? steps : undefined
            }
            onSave={(newSteps) => setSteps(newSteps)}
          />
        </div>
      )}

      {/* Form mode: Steps */}
      {mode === "form" && (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-medium text-zinc-500">
            Pipeline Steps
          </label>
          <button
            onClick={addStep}
            className="flex items-center gap-1 px-2 py-1 text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            <Plus className="w-3 h-3" />
            Add Step
          </button>
        </div>
        {steps.map((step, i) => (
          <div
            key={i}
            className="flex items-start gap-2 p-3 bg-zinc-950 border border-zinc-800 rounded-lg"
          >
            <span className="text-xs text-zinc-600 mt-2 w-6 shrink-0">
              #{i + 1}
            </span>
            <div className="flex-1 space-y-2">
              <select
                value={step.agent_name}
                onChange={(e) => updateStep(i, "agent_name", e.target.value)}
                className="w-full px-2 py-1.5 bg-zinc-900 border border-zinc-700 rounded text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="">Select agent...</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.name}>
                    {a.name} ({a.role})
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={step.prompt_template}
                onChange={(e) =>
                  updateStep(i, "prompt_template", e.target.value)
                }
                placeholder="Prompt template (use {input} for previous output)"
                className="w-full px-2 py-1.5 bg-zinc-900 border border-zinc-700 rounded text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
              />
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={step.requires_approval ?? false}
                  onChange={(e) =>
                    updateStep(i, "requires_approval", e.target.checked)
                  }
                  className="w-3.5 h-3.5 rounded border-zinc-600 bg-zinc-900 text-amber-500 focus:ring-amber-500"
                />
                <span className="text-xs text-amber-400">
                  Require approval before next step
                </span>
              </label>
            </div>
            {steps.length > 1 && (
              <button
                onClick={() => removeStep(i)}
                className="mt-2 text-zinc-600 hover:text-red-400 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        ))}
      </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2">
        <button
          onClick={() => void handleSubmit()}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50"
        >
          <Check className="w-3 h-3" />
          {saving ? "Creating..." : "Create Workflow"}
        </button>
        <button
          onClick={onCancel}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-800 border border-zinc-700 rounded-lg transition-colors"
        >
          <X className="w-3 h-3" />
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── Workflow Card ────────────────────────────────────────────────────

function WorkflowCard({
  workflow,
  expanded,
  onToggle,
  onDelete,
  onRunComplete,
}: {
  workflow: Workflow;
  expanded: boolean;
  onToggle: () => void;
  onDelete: (id: string) => Promise<void>;
  onRunComplete: () => void;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showRun, setShowRun] = useState(false);
  const [runInput, setRunInput] = useState("");
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<WorkflowRunResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);

  const isAwaitingApproval = workflow.status === "awaiting_approval";

  const handleRun = async () => {
    if (!runInput.trim()) return;
    setRunning(true);
    setRunError(null);
    setRunResult(null);
    try {
      const result = await runWorkflow(workflow.id, runInput.trim());
      setRunResult(result);
      onRunComplete();
    } catch (err) {
      setRunError(
        err instanceof Error ? err.message : "Workflow execution failed"
      );
    } finally {
      setRunning(false);
    }
  };

  const handleApprove = async () => {
    setApproving(true);
    setRunError(null);
    try {
      const result = await approveWorkflow(workflow.id);
      setRunResult(result);
      onRunComplete();
    } catch (err) {
      setRunError(
        err instanceof Error ? err.message : "Approval failed"
      );
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async () => {
    setRejecting(true);
    setRunError(null);
    try {
      const result = await rejectWorkflow(workflow.id);
      setRunResult(result);
      onRunComplete();
    } catch (err) {
      setRunError(
        err instanceof Error ? err.message : "Rejection failed"
      );
    } finally {
      setRejecting(false);
    }
  };

  const steps: WorkflowStep[] = Array.isArray(workflow.steps)
    ? workflow.steps
    : [];

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
            <GitBranch className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-medium text-zinc-200">
              {workflow.name}
            </span>
            <span className="px-1.5 py-0.5 text-xs rounded border bg-zinc-800 text-zinc-400 border-zinc-700">
              {steps.length} step{steps.length !== 1 ? "s" : ""}
            </span>
            {isAwaitingApproval && (
              <span className="px-1.5 py-0.5 text-xs rounded border bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse">
                Awaiting Approval
              </span>
            )}
          </div>
          <p className="text-xs text-zinc-500 mt-0.5 truncate">
            {workflow.description || "No description"}
          </p>
        </div>

        <div className="flex items-center gap-6 text-xs text-zinc-400">
          <span className="flex items-center gap-1">
            <Zap className="w-3 h-3" />
            {workflow.total_runs} runs
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {workflow.last_run_at
              ? new Date(workflow.last_run_at).toLocaleDateString()
              : "Never"}
          </span>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-zinc-800 px-4 py-4 space-y-4">
          {/* Approval banner */}
          {isAwaitingApproval && (
            <div className="flex items-center gap-3 p-3 bg-amber-500/5 border border-amber-500/20 rounded-lg">
              <span className="text-xs text-amber-400 flex-1">
                This workflow is paused and awaiting your approval to
                continue.
              </span>
              <button
                onClick={() => void handleApprove()}
                disabled={approving || rejecting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50"
              >
                {approving ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Check className="w-3 h-3" />
                )}
                {approving ? "Approving..." : "Approve"}
              </button>
              <button
                onClick={() => void handleReject()}
                disabled={approving || rejecting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-400 hover:text-red-300 bg-red-500/10 border border-red-500/20 rounded-lg transition-colors disabled:opacity-50"
              >
                {rejecting ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <X className="w-3 h-3" />
                )}
                {rejecting ? "Rejecting..." : "Reject"}
              </button>
            </div>
          )}

          {runError && (
            <div className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded text-xs text-red-400">
              {runError}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            {!confirmDelete && (
              <>
                <button
                  onClick={() => setShowRun(!showRun)}
                  disabled={isAwaitingApproval}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-emerald-400 hover:text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 rounded-lg transition-colors disabled:opacity-50"
                >
                  <Play className="w-3 h-3" />
                  Run
                </button>
                <button
                  onClick={() => setConfirmDelete(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-red-400 hover:text-red-300 bg-zinc-800 border border-zinc-700 rounded-lg transition-colors"
                >
                  <Trash2 className="w-3 h-3" />
                  Delete
                </button>
              </>
            )}
            {confirmDelete && (
              <div className="flex items-center gap-3 px-3 py-2 bg-red-500/5 border border-red-500/20 rounded-lg">
                <span className="text-xs text-red-400">
                  Delete <strong>{workflow.name}</strong>?
                </span>
                <button
                  onClick={async () => {
                    setDeleting(true);
                    try {
                      await onDelete(workflow.id);
                    } finally {
                      setDeleting(false);
                      setConfirmDelete(false);
                    }
                  }}
                  disabled={deleting}
                  className="px-3 py-1 text-xs font-medium text-white bg-red-600 hover:bg-red-500 rounded transition-colors disabled:opacity-50"
                >
                  {deleting ? "Deleting..." : "Confirm"}
                </button>
                <button
                  onClick={() => setConfirmDelete(false)}
                  disabled={deleting}
                  className="px-3 py-1 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>

          {/* Pipeline visualization */}
          <div>
            <h4 className="text-xs font-medium text-zinc-500 mb-2">
              Pipeline
            </h4>
            <div className="space-y-1">
              {steps.map((step, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-xs text-zinc-600 w-6 shrink-0">
                    #{i + 1}
                  </span>
                  <div className="flex-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg">
                    <span className="text-xs text-emerald-400 font-medium">
                      {step.agent_name}
                    </span>
                    <span className="text-xs text-zinc-600 ml-2">
                      {step.prompt_template}
                    </span>
                    {step.requires_approval && (
                      <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        approval
                      </span>
                    )}
                  </div>
                  {i < steps.length - 1 && (
                    <span className="text-zinc-600 text-xs">→</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Run panel */}
          {showRun && (
            <div className="space-y-3 p-3 bg-zinc-950 border border-zinc-800 rounded-lg">
              <h4 className="text-xs font-medium text-zinc-400">
                Run Workflow
              </h4>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={runInput}
                  onChange={(e) => setRunInput(e.target.value)}
                  placeholder="Enter initial input for the pipeline..."
                  className="flex-1 px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !running) void handleRun();
                  }}
                />
                <button
                  onClick={() => void handleRun()}
                  disabled={running || !runInput.trim()}
                  className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50"
                >
                  {running ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Play className="w-3 h-3" />
                  )}
                  {running ? "Running..." : "Execute"}
                </button>
              </div>

              {runError && (
                <div className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded text-xs text-red-400">
                  {runError}
                </div>
              )}

              {runResult && (
                <>
                  <RunResultView result={runResult} />
                  {/* Execution visualization */}
                  <div className="h-[300px] mt-3">
                    <WorkflowCanvas
                      agents={[]}
                      initialSteps={steps}
                      readOnly
                      executionStatus={Object.fromEntries(
                        runResult.steps.map((s) => [
                          s.step,
                          runResult.status === "awaiting_approval" &&
                          s.step === runResult.steps.length - 1
                            ? ("complete" as const)
                            : ("complete" as const),
                        ])
                      )}
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Run Result View ─────────────────────────────────────────────────

function RunResultView({ result }: { result: WorkflowRunResult }) {
  const status = result.status ?? "completed";
  const statusColor =
    status === "awaiting_approval"
      ? "text-amber-400"
      : status === "rejected"
        ? "text-red-400"
        : "text-emerald-400";

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4 text-xs text-zinc-400">
        <span className={statusColor}>
          {status === "awaiting_approval"
            ? "Paused"
            : status === "rejected"
              ? "Rejected"
              : "Completed"}
        </span>
        <span>
          {result.total_steps} step{result.total_steps !== 1 ? "s" : ""}{" "}
          completed
        </span>
        <span>
          {result.steps.reduce((sum, s) => sum + s.tokens, 0).toLocaleString()}{" "}
          total tokens
        </span>
        <span>
          {(
            result.steps.reduce((sum, s) => sum + s.latency_ms, 0) / 1000
          ).toFixed(1)}
          s total
        </span>
      </div>

      {result.steps.map((step) => (
        <div
          key={step.step}
          className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg space-y-2"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-emerald-400">
              Step {step.step + 1}: {step.agent_name}
            </span>
            <span className="text-xs text-zinc-500">
              {step.tokens} tok &middot;{" "}
              {(step.latency_ms / 1000).toFixed(1)}s
            </span>
          </div>
          <pre className="text-xs text-zinc-300 whitespace-pre-wrap max-h-40 overflow-y-auto">
            {step.output}
          </pre>
        </div>
      ))}

      <div className="p-3 bg-emerald-500/5 border border-emerald-500/20 rounded-lg">
        <h5 className="text-xs font-medium text-emerald-400 mb-1">
          Final Output
        </h5>
        <pre className="text-xs text-zinc-300 whitespace-pre-wrap max-h-48 overflow-y-auto">
          {result.final_output}
        </pre>
      </div>
    </div>
  );
}

// ── Shared Components ───────────────────────────────────────────────

function FormField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-zinc-500 mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}
