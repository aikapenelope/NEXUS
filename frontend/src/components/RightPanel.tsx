"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Bot,
  Brain,
  Database,
  RefreshCw,
  Trash2,
  Activity,
  Wrench,
  Check,
} from "lucide-react";
import type { NexusState, RegistryAgent, AgentActivity } from "@/lib/types";
import { fetchAgents, deleteAgent, fetchTools, type ToolInfo } from "@/lib/api";

interface RightPanelProps {
  state: NexusState | undefined;
}

export function RightPanel({ state }: RightPanelProps) {
  if (!state) return null;

  const panel = state.active_panel;
  if (panel === "chat") return null;

  return (
    <aside className="w-80 border-l border-zinc-800 bg-zinc-950 overflow-y-auto">
      <div className="p-4">
        {panel === "agents" && <AgentPanel state={state} />}
        {panel === "cerebro" && <CerebroPanel state={state} />}
        {panel === "memory" && <MemoryPanel state={state} />}
        {panel === "tools" && <ToolsPanel />}
        {panel === "activity" && <ActivityFeedPanel state={state} />}
      </div>
    </aside>
  );
}

// ── Agent Panel (current agent + registry list) ─────────────────────

function AgentPanel({ state }: { state: NexusState }) {
  const agent = state.current_agent;
  const [registryAgents, setRegistryAgents] = useState<RegistryAgent[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const loadAgents = useCallback(async () => {
    setLoading(true);
    try {
      const agents = await fetchAgents();
      setRegistryAgents(agents);
    } catch {
      // Silently fail — API may not be reachable yet
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAgents();
  }, [loadAgents]);

  const handleDelete = async (agentId: string) => {
    await deleteAgent(agentId);
    setRegistryAgents((prev) => prev.filter((a) => a.id !== agentId));
    if (selectedId === agentId) setSelectedId(null);
  };

  const selected = registryAgents.find((a) => a.id === selectedId);

  return (
    <div className="space-y-4">
      {/* Current agent from AG-UI state */}
      {agent.name && (
        <div>
          <h3 className="text-sm font-medium text-zinc-300 mb-2 flex items-center gap-2">
            <Bot className="w-4 h-4" /> Current Agent
          </h3>
          <CurrentAgentCard agent={agent} />
        </div>
      )}

      {/* Registry agents */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
            <Database className="w-4 h-4" /> Saved Agents
          </h3>
          <button
            onClick={() => void loadAgents()}
            disabled={loading}
            className="p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {registryAgents.length === 0 && !loading && (
          <p className="text-zinc-500 text-xs">
            No agents saved yet. Build one via chat.
          </p>
        )}

        <div className="space-y-1.5">
          {registryAgents.map((a) => (
            <button
              key={a.id}
              onClick={() => setSelectedId(selectedId === a.id ? null : a.id)}
              className={`w-full text-left p-2 rounded border transition-colors ${
                selectedId === a.id
                  ? "border-emerald-500/50 bg-emerald-500/5"
                  : "border-zinc-800 bg-zinc-900 hover:border-zinc-700"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-zinc-200 truncate">{a.name}</span>
                <span className="text-xs text-zinc-500">{a.role}</span>
              </div>
              <p className="text-xs text-zinc-500 truncate mt-0.5">{a.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Selected agent detail */}
      {selected && (
        <AgentDetail agent={selected} onDelete={handleDelete} />
      )}
    </div>
  );
}

function CurrentAgentCard({ agent }: { agent: NexusState["current_agent"] }) {
  return (
    <div className="p-2 bg-zinc-900 rounded border border-zinc-800 space-y-1.5 text-sm">
      <div className="flex justify-between">
        <span className="text-zinc-500">Name</span>
        <span className="text-zinc-200">{agent.name}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-zinc-500">Role</span>
        <span className="text-zinc-200">{agent.model}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-zinc-500">Status</span>
        <span className={agent.status === "ready" ? "text-emerald-400" : "text-zinc-400"}>
          {agent.status}
        </span>
      </div>
      {agent.tools.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-1">
          {agent.tools.map((tool) => (
            <span key={tool} className="px-2 py-0.5 bg-zinc-800 rounded text-xs text-zinc-300">
              {tool}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function AgentDetail({
  agent,
  onDelete,
}: {
  agent: RegistryAgent;
  onDelete: (id: string) => Promise<void>;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const enabledTools: string[] = [];
  if (agent.include_todo) enabledTools.push("todo");
  if (agent.include_filesystem) enabledTools.push("filesystem");
  if (agent.include_subagents) enabledTools.push("subagents");
  if (agent.include_skills) enabledTools.push("skills");
  if (agent.include_memory) enabledTools.push("memory");
  if (agent.include_web) enabledTools.push("web");

  const handleConfirmDelete = async () => {
    setDeleting(true);
    try {
      await onDelete(agent.id);
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  return (
    <div className="p-3 bg-zinc-900 rounded border border-zinc-800 space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-zinc-200">{agent.name}</h4>
        {!confirmDelete && (
          <button
            onClick={() => setConfirmDelete(true)}
            className="p-1 text-zinc-500 hover:text-red-400 transition-colors"
            title="Delete agent"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {confirmDelete && (
        <div className="flex items-center gap-2 p-2 bg-red-500/5 border border-red-500/20 rounded text-xs">
          <span className="text-red-400 flex-1">Delete this agent?</span>
          <button
            onClick={() => void handleConfirmDelete()}
            disabled={deleting}
            className="px-2 py-0.5 text-white bg-red-600 hover:bg-red-500 rounded transition-colors disabled:opacity-50"
          >
            {deleting ? "..." : "Yes"}
          </button>
          <button
            onClick={() => setConfirmDelete(false)}
            disabled={deleting}
            className="px-2 py-0.5 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            No
          </button>
        </div>
      )}

      <p className="text-xs text-zinc-400">{agent.description}</p>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <span className="text-zinc-500">Role</span>
        <span className="text-zinc-300">{agent.role}</span>

        <span className="text-zinc-500">Status</span>
        <span className={agent.status === "ready" ? "text-emerald-400" : "text-zinc-400"}>
          {agent.status}
        </span>

        <span className="text-zinc-500">Runs</span>
        <span className="text-zinc-300">{agent.total_runs}</span>

        <span className="text-zinc-500">Tokens</span>
        <span className="text-zinc-300">{agent.total_tokens.toLocaleString()}</span>

        <span className="text-zinc-500">Created</span>
        <span className="text-zinc-300">
          {new Date(agent.created_at).toLocaleDateString()}
        </span>

        {agent.last_run_at && (
          <>
            <span className="text-zinc-500">Last run</span>
            <span className="text-zinc-300">
              {new Date(agent.last_run_at).toLocaleDateString()}
            </span>
          </>
        )}
      </div>

      {enabledTools.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-1">
          {enabledTools.map((tool) => (
            <span key={tool} className="px-2 py-0.5 bg-zinc-800 rounded text-xs text-zinc-300">
              {tool}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Cerebro Panel ───────────────────────────────────────────────────

function CerebroPanel({ state }: { state: NexusState }) {
  const stages = state.cerebro_stages;
  if (stages.length === 0) {
    return (
      <div className="text-zinc-500 text-sm">
        <Brain className="w-5 h-5 mb-2" />
        No Cerebro pipeline running. Ask NEXUS to analyze a topic.
      </div>
    );
  }
  return (
    <div>
      <h3 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
        <Brain className="w-4 h-4" /> Cerebro Pipeline
      </h3>
      <div className="space-y-3">
        {stages.map((stage, i) => (
          <div key={i} className="flex items-start gap-2">
            <div
              className={`w-2 h-2 rounded-full mt-1.5 ${
                stage.status === "completed"
                  ? "bg-emerald-400"
                  : stage.status === "running"
                    ? "bg-amber-400 animate-pulse"
                    : "bg-zinc-600"
              }`}
            />
            <div className="flex-1 min-w-0">
              <div className="text-sm text-zinc-300">{stage.name}</div>
              {stage.output && (
                <div className="text-xs text-zinc-500 mt-0.5 truncate">{stage.output}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Memory Panel ────────────────────────────────────────────────────

function MemoryPanel({ state }: { state: NexusState }) {
  const memories = state.memories;
  if (memories.length === 0) {
    return (
      <div className="text-zinc-500 text-sm">
        <Database className="w-5 h-5 mb-2" />
        No memories loaded. Ask NEXUS to search memory.
      </div>
    );
  }
  return (
    <div>
      <h3 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
        <Database className="w-4 h-4" /> Memories ({memories.length})
      </h3>
      <div className="space-y-2">
        {memories.map((mem) => (
          <div key={mem.id} className="p-2 bg-zinc-900 rounded border border-zinc-800">
            <div className="text-sm text-zinc-300">{mem.memory}</div>
            <div className="text-xs text-zinc-500 mt-1">
              Score: {mem.score.toFixed(2)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Tools Panel ─────────────────────────────────────────────────────

function ToolsPanel() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const loadTools = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchTools();
      setTools(data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTools();
  }, [loadTools]);

  const readyCount = tools.filter((t) => t.configured && t.enabled).length;

  // Group by category
  const categories: Record<string, ToolInfo[]> = {};
  for (const t of tools) {
    (categories[t.category] ??= []).push(t);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
          <Wrench className="w-4 h-4" /> Tools ({readyCount}/{tools.length})
        </h3>
        <button
          onClick={() => void loadTools()}
          disabled={loading}
          className="p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
          title="Refresh"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
          />
        </button>
      </div>

      {loading && tools.length === 0 ? (
        <p className="text-zinc-500 text-xs">Loading tools...</p>
      ) : tools.length === 0 ? (
        <p className="text-zinc-500 text-xs">
          No tools available. Configure them in the dashboard.
        </p>
      ) : (
        <div className="space-y-3">
          {Object.entries(categories)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([cat, catTools]) => (
              <div key={cat}>
                <h4 className="text-xs font-medium text-zinc-500 mb-1">
                  {cat}
                </h4>
                <div className="space-y-1">
                  {catTools.map((t) => {
                    const isReady = t.configured && t.enabled;
                    return (
                      <div
                        key={t.id}
                        className={`flex items-center gap-2 px-2 py-1.5 rounded border text-xs ${
                          isReady
                            ? "border-emerald-500/20 bg-emerald-500/5"
                            : "border-zinc-800 bg-zinc-900"
                        }`}
                      >
                        {isReady ? (
                          <Check className="w-3 h-3 text-emerald-400 shrink-0" />
                        ) : (
                          <Wrench className="w-3 h-3 text-zinc-600 shrink-0" />
                        )}
                        <span
                          className={`truncate ${
                            isReady ? "text-zinc-200" : "text-zinc-500"
                          }`}
                        >
                          {t.name}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

// ── Activity Feed Panel ─────────────────────────────────────────────

const EVENT_CONFIG: Record<
  string,
  { color: string; bg: string; border: string; icon: string }
> = {
  start: {
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/20",
    icon: "▶",
  },
  tool_call: {
    color: "text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/20",
    icon: "◉",
  },
  complete: {
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/20",
    icon: "✓",
  },
  error: {
    color: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/20",
    icon: "✗",
  },
  info: {
    color: "text-zinc-400",
    bg: "bg-zinc-800",
    border: "border-zinc-700",
    icon: "•",
  },
};

function formatEventTime(timestamp: string): string {
  if (!timestamp) return "";
  try {
    const d = new Date(timestamp);
    return d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}

function ActivityFeedPanel({ state }: { state: NexusState }) {
  const events: AgentActivity[] = state.activity_log ?? [];
  // Show newest first
  const sorted = [...events].reverse();

  if (sorted.length === 0) {
    return (
      <div className="text-zinc-500 text-sm">
        <Activity className="w-5 h-5 mb-2" />
        No agent activity yet. Run an agent to see live events.
      </div>
    );
  }

  return (
    <div>
      <h3 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
        <Activity className="w-4 h-4" /> Activity Feed ({sorted.length})
      </h3>
      <div className="space-y-1.5">
        {sorted.map((event, i) => {
          const cfg = EVENT_CONFIG[event.event_type] ?? EVENT_CONFIG.info;
          return (
            <div
              key={`${event.timestamp}-${i}`}
              className={`p-2 rounded border ${cfg.bg} ${cfg.border}`}
            >
              <div className="flex items-center gap-2">
                <span className={`text-xs font-mono ${cfg.color}`}>
                  {cfg.icon}
                </span>
                <span className="text-xs font-medium text-zinc-200 truncate flex-1">
                  {event.agent_name}
                </span>
                <span className="text-xs text-zinc-500 shrink-0">
                  {formatEventTime(event.timestamp)}
                </span>
              </div>
              {event.detail && (
                <p className="text-xs text-zinc-400 mt-1 truncate pl-5">
                  {event.detail}
                </p>
              )}
              {(event.tokens > 0 || event.latency_ms > 0) && (
                <div className="flex gap-3 mt-1 pl-5">
                  {event.tokens > 0 && (
                    <span className="text-xs text-zinc-500">
                      {event.tokens.toLocaleString()} tok
                    </span>
                  )}
                  {event.latency_ms > 0 && (
                    <span className="text-xs text-zinc-500">
                      {(event.latency_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
