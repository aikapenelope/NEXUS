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
  Pencil,
  Trash2,
  X,
  Check,
  Plus,
} from "lucide-react";
import type { RegistryAgent } from "@/lib/types";
import { fetchAgents, updateAgent, deleteAgent, createAgent } from "@/lib/api";
import type { CreateAgentPayload } from "@/lib/api";

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
  const [showCreate, setShowCreate] = useState(false);

  const loadAgents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAgents();
      setAgents(data);
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

  const handleUpdate = async (agentId: string, updates: Partial<RegistryAgent>) => {
    const updated = await updateAgent(agentId, updates);
    setAgents((prev) => prev.map((a) => (a.id === agentId ? updated : a)));
  };

  const handleDelete = async (agentId: string) => {
    await deleteAgent(agentId);
    setAgents((prev) => prev.filter((a) => a.id !== agentId));
    if (expandedId === agentId) {
      setExpandedId(null);
      setAgentRuns([]);
    }
  };

  const handleCreate = async (payload: CreateAgentPayload) => {
    const newAgent = await createAgent(payload);
    setAgents((prev) => [newAgent, ...prev]);
    setShowCreate(false);
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
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            New Agent
          </button>
          <button
            onClick={() => void loadAgents()}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-200 bg-zinc-900 border border-zinc-800 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Create agent form */}
      {showCreate && (
        <CreateAgentForm
          onCreate={handleCreate}
          onCancel={() => setShowCreate(false)}
        />
      )}

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
              onUpdate={handleUpdate}
              onDelete={handleDelete}
              runs={expandedId === agent.id ? agentRuns : []}
              runsLoading={runsLoading && expandedId === agent.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Create Agent Form ───────────────────────────────────────────────

function CreateAgentForm({
  onCreate,
  onCancel,
}: {
  onCreate: (payload: CreateAgentPayload) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [role, setRole] = useState("worker");
  const [tools, setTools] = useState({
    include_todo: false,
    include_filesystem: false,
    include_subagents: false,
    include_skills: false,
    include_memory: false,
    include_web: false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleTool = (key: keyof typeof tools) => {
    setTools((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    if (!description.trim()) {
      setError("Description is required");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await onCreate({
        name: name.trim(),
        description: description.trim(),
        instructions: instructions.trim(),
        role,
        ...tools,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create agent");
    } finally {
      setSaving(false);
    }
  };

  const toolEntries: { key: keyof typeof tools; label: string }[] = [
    { key: "include_todo", label: "Todo" },
    { key: "include_filesystem", label: "Filesystem" },
    { key: "include_subagents", label: "Subagents" },
    { key: "include_skills", label: "Skills" },
    { key: "include_memory", label: "Memory" },
    { key: "include_web", label: "Web" },
  ];

  return (
    <div className="bg-zinc-900 border border-emerald-500/30 rounded-xl p-4 space-y-4">
      <h3 className="text-sm font-medium text-zinc-200 flex items-center gap-2">
        <Plus className="w-4 h-4 text-emerald-400" />
        Create New Agent
      </h3>

      {error && (
        <div className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        {/* Left column */}
        <div className="space-y-3">
          <FormField label="Name">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-agent"
              className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-700 rounded text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
            />
          </FormField>
          <FormField label="Role">
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-700 rounded text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="worker">worker (Groq gpt-oss-20b, fast + cheap)</option>
              <option value="analysis">analysis (Claude Haiku, smarter)</option>
              <option value="builder">builder (Claude Haiku)</option>
            </select>
          </FormField>
          <FormField label="Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="What does this agent do?"
              className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-700 rounded text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500 resize-none"
            />
          </FormField>
        </div>

        {/* Right column */}
        <div className="space-y-3">
          <FormField label="Instructions (system prompt)">
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={6}
              placeholder="You are an expert at..."
              className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-700 rounded text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500 resize-none"
            />
          </FormField>
          <FormField label="Tools">
            <div className="flex flex-wrap gap-2">
              {toolEntries.map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleTool(key)}
                  className={`px-2 py-1 text-xs rounded border transition-colors ${
                    tools[key]
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      : "bg-zinc-800 text-zinc-500 border-zinc-700"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </FormField>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2">
        <button
          onClick={() => void handleSubmit()}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50"
        >
          <Check className="w-3 h-3" />
          {saving ? "Creating..." : "Create Agent"}
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

// ── Agent Card ──────────────────────────────────────────────────────

function AgentCard({
  agent,
  expanded,
  onToggle,
  onUpdate,
  onDelete,
  runs,
  runsLoading,
}: {
  agent: RegistryAgent;
  expanded: boolean;
  onToggle: () => void;
  onUpdate: (id: string, updates: Partial<RegistryAgent>) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  runs: RunTrace[];
  runsLoading: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const enabledTools = getEnabledTools(agent);

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
          {/* Action buttons */}
          <div className="flex items-center gap-2">
            {!editing && !confirmDelete && (
              <>
                <button
                  onClick={() => setEditing(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-800 border border-zinc-700 rounded-lg transition-colors"
                >
                  <Pencil className="w-3 h-3" />
                  Edit
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
              <DeleteConfirm
                agentName={agent.name}
                deleting={deleting}
                onConfirm={async () => {
                  setDeleting(true);
                  try {
                    await onDelete(agent.id);
                  } finally {
                    setDeleting(false);
                    setConfirmDelete(false);
                  }
                }}
                onCancel={() => setConfirmDelete(false)}
              />
            )}
          </div>

          {/* Edit form or read-only view */}
          {editing ? (
            <EditForm
              agent={agent}
              saving={saving}
              onSave={async (updates) => {
                setSaving(true);
                try {
                  await onUpdate(agent.id, updates);
                  setEditing(false);
                } finally {
                  setSaving(false);
                }
              }}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <AgentReadView agent={agent} enabledTools={enabledTools} />
          )}

          {/* Run history */}
          <RunHistory runs={runs} loading={runsLoading} />
        </div>
      )}
    </div>
  );
}

// ── Edit Form ───────────────────────────────────────────────────────

function EditForm({
  agent,
  saving,
  onSave,
  onCancel,
}: {
  agent: RegistryAgent;
  saving: boolean;
  onSave: (updates: Partial<RegistryAgent>) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(agent.name);
  const [description, setDescription] = useState(agent.description);
  const [instructions, setInstructions] = useState(agent.instructions);
  const [role, setRole] = useState(agent.role);
  const [tools, setTools] = useState({
    include_todo: agent.include_todo,
    include_filesystem: agent.include_filesystem,
    include_subagents: agent.include_subagents,
    include_skills: agent.include_skills,
    include_memory: agent.include_memory,
    include_web: agent.include_web,
  });

  const toggleTool = (key: keyof typeof tools) => {
    setTools((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSubmit = async () => {
    const updates: Partial<RegistryAgent> = {};
    if (name !== agent.name) updates.name = name;
    if (description !== agent.description) updates.description = description;
    if (instructions !== agent.instructions) updates.instructions = instructions;
    if (role !== agent.role) updates.role = role;
    if (tools.include_todo !== agent.include_todo) updates.include_todo = tools.include_todo;
    if (tools.include_filesystem !== agent.include_filesystem)
      updates.include_filesystem = tools.include_filesystem;
    if (tools.include_subagents !== agent.include_subagents)
      updates.include_subagents = tools.include_subagents;
    if (tools.include_skills !== agent.include_skills)
      updates.include_skills = tools.include_skills;
    if (tools.include_memory !== agent.include_memory)
      updates.include_memory = tools.include_memory;
    if (tools.include_web !== agent.include_web) updates.include_web = tools.include_web;

    if (Object.keys(updates).length === 0) {
      onCancel();
      return;
    }
    await onSave(updates);
  };

  const toolEntries: { key: keyof typeof tools; label: string }[] = [
    { key: "include_todo", label: "Todo" },
    { key: "include_filesystem", label: "Filesystem" },
    { key: "include_subagents", label: "Subagents" },
    { key: "include_skills", label: "Skills" },
    { key: "include_memory", label: "Memory" },
    { key: "include_web", label: "Web" },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        {/* Left column */}
        <div className="space-y-3">
          <FormField label="Name">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-700 rounded text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
            />
          </FormField>
          <FormField label="Role">
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-700 rounded text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="worker">worker</option>
              <option value="analysis">analysis</option>
              <option value="builder">builder</option>
            </select>
          </FormField>
          <FormField label="Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-700 rounded text-sm text-zinc-200 focus:outline-none focus:border-emerald-500 resize-none"
            />
          </FormField>
        </div>

        {/* Right column */}
        <div className="space-y-3">
          <FormField label="Instructions">
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={6}
              className="w-full px-2 py-1.5 bg-zinc-950 border border-zinc-700 rounded text-sm text-zinc-200 focus:outline-none focus:border-emerald-500 resize-none"
            />
          </FormField>
          <FormField label="Tools">
            <div className="flex flex-wrap gap-2">
              {toolEntries.map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleTool(key)}
                  className={`px-2 py-1 text-xs rounded border transition-colors ${
                    tools[key]
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      : "bg-zinc-800 text-zinc-500 border-zinc-700"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </FormField>
        </div>
      </div>

      {/* Save / Cancel */}
      <div className="flex items-center gap-2 pt-2">
        <button
          onClick={() => void handleSubmit()}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50"
        >
          <Check className="w-3 h-3" />
          {saving ? "Saving..." : "Save"}
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

// ── Delete Confirmation ─────────────────────────────────────────────

function DeleteConfirm({
  agentName,
  deleting,
  onConfirm,
  onCancel,
}: {
  agentName: string;
  deleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="flex items-center gap-3 px-3 py-2 bg-red-500/5 border border-red-500/20 rounded-lg">
      <span className="text-xs text-red-400">
        Delete <strong>{agentName}</strong>? This cannot be undone.
      </span>
      <button
        onClick={onConfirm}
        disabled={deleting}
        className="px-3 py-1 text-xs font-medium text-white bg-red-600 hover:bg-red-500 rounded transition-colors disabled:opacity-50"
      >
        {deleting ? "Deleting..." : "Confirm"}
      </button>
      <button
        onClick={onCancel}
        disabled={deleting}
        className="px-3 py-1 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
      >
        Cancel
      </button>
    </div>
  );
}

// ── Read-only Agent View ────────────────────────────────────────────

function AgentReadView({
  agent,
  enabledTools,
}: {
  agent: RegistryAgent;
  enabledTools: string[];
}) {
  return (
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
  );
}

// ── Run History ─────────────────────────────────────────────────────

function RunHistory({ runs, loading }: { runs: RunTrace[]; loading: boolean }) {
  return (
    <div>
      <h4 className="text-xs font-medium text-zinc-500 mb-2">Recent Runs</h4>
      {loading ? (
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
      <label className="block text-xs font-medium text-zinc-500 mb-1">{label}</label>
      {children}
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

// ── Helpers ─────────────────────────────────────────────────────────

function getEnabledTools(agent: RegistryAgent): string[] {
  const tools: string[] = [];
  if (agent.include_todo) tools.push("todo");
  if (agent.include_filesystem) tools.push("filesystem");
  if (agent.include_subagents) tools.push("subagents");
  if (agent.include_skills) tools.push("skills");
  if (agent.include_memory) tools.push("memory");
  if (agent.include_web) tools.push("web");
  return tools;
}
