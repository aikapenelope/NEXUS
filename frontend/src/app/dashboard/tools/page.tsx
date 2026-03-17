"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Search,
  Globe,
  Database,
  MessageSquare,
  FileText,
  Server,
  RefreshCw,
  Check,
  X,
  Settings,
  Wrench,
} from "lucide-react";
import {
  fetchTools,
  configureTool,
  type ToolInfo,
} from "@/lib/api";

// ── Category icons ──────────────────────────────────────────────────

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  Search: Search,
  Web: Globe,
  Data: Database,
  Communication: MessageSquare,
  Files: FileText,
  MCP: Server,
};

// ── Page ────────────────────────────────────────────────────────────

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [configTool, setConfigTool] = useState<ToolInfo | null>(null);

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

  const categories = [...new Set(tools.map((t) => t.category))];
  const filtered = activeCategory
    ? tools.filter((t) => t.category === activeCategory)
    : tools;

  const configuredCount = tools.filter((t) => t.configured).length;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">
            Tool Registry
          </h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            {configuredCount} of {tools.length} tools configured
          </p>
        </div>
        <button
          onClick={() => void loadTools()}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-200 bg-zinc-900 border border-zinc-800 rounded-lg transition-colors"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
          />
          Refresh
        </button>
      </div>

      {/* Category filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setActiveCategory(null)}
          className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
            activeCategory === null
              ? "bg-emerald-600 text-zinc-100 border-emerald-500"
              : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200"
          }`}
        >
          All
        </button>
        {categories.map((cat) => {
          const Icon = CATEGORY_ICONS[cat] ?? Wrench;
          return (
            <button
              key={cat}
              onClick={() =>
                setActiveCategory(activeCategory === cat ? null : cat)
              }
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                activeCategory === cat
                  ? "bg-emerald-600 text-zinc-100 border-emerald-500"
                  : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200"
              }`}
            >
              <Icon className="w-3 h-3" />
              {cat}
            </button>
          );
        })}
      </div>

      {/* Tool grid */}
      {loading && tools.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-zinc-600">
          Loading tools...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((tool) => (
            <ToolCard
              key={tool.id}
              tool={tool}
              onConfigure={() => setConfigTool(tool)}
            />
          ))}
        </div>
      )}

      {/* Config modal */}
      {configTool && (
        <ConfigModal
          tool={configTool}
          onClose={() => setConfigTool(null)}
          onSave={async (config) => {
            await configureTool(configTool.id, config);
            setConfigTool(null);
            void loadTools();
          }}
        />
      )}
    </div>
  );
}

// ── Tool Card ───────────────────────────────────────────────────────

function ToolCard({
  tool,
  onConfigure,
}: {
  tool: ToolInfo;
  onConfigure: () => void;
}) {
  const Icon = CATEGORY_ICONS[tool.category] ?? Wrench;
  const isReady = tool.configured && tool.enabled;

  return (
    <div
      className={`p-4 rounded-xl border transition-colors ${
        isReady
          ? "bg-zinc-900 border-emerald-500/20"
          : "bg-zinc-900 border-zinc-800"
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`p-2 rounded-lg ${
            isReady ? "bg-emerald-500/10" : "bg-zinc-800"
          }`}
        >
          <Icon
            className={`w-4 h-4 ${
              isReady ? "text-emerald-400" : "text-zinc-500"
            }`}
          />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-zinc-200">
              {tool.name}
            </span>
            {isReady ? (
              <span className="flex items-center gap-0.5 px-1.5 py-0.5 text-xs rounded bg-emerald-500/10 text-emerald-400">
                <Check className="w-3 h-3" />
                Ready
              </span>
            ) : tool.requires_config ? (
              <span className="px-1.5 py-0.5 text-xs rounded bg-amber-500/10 text-amber-400">
                Needs Config
              </span>
            ) : (
              <span className="px-1.5 py-0.5 text-xs rounded bg-zinc-800 text-zinc-500">
                Available
              </span>
            )}
          </div>
          <p className="text-xs text-zinc-500 mt-1">{tool.description}</p>
          <div className="flex items-center gap-2 mt-2">
            <span className="px-1.5 py-0.5 text-xs rounded bg-zinc-800 text-zinc-500">
              {tool.category}
            </span>
            {tool.built_in && (
              <span className="px-1.5 py-0.5 text-xs rounded bg-zinc-800 text-zinc-500">
                Built-in
              </span>
            )}
          </div>
        </div>
      </div>
      {tool.requires_config && (
        <button
          onClick={onConfigure}
          className="mt-3 w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs text-zinc-300 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-lg transition-colors"
        >
          <Settings className="w-3 h-3" />
          Configure
        </button>
      )}
    </div>
  );
}

// ── Config Modal ────────────────────────────────────────────────────

function ConfigModal({
  tool,
  onClose,
  onSave,
}: {
  tool: ToolInfo;
  onClose: () => void;
  onSave: (config: Record<string, string>) => Promise<void>;
}) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const field of tool.config_fields) {
      init[field] = "";
    }
    return init;
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    // Validate all fields are filled
    const empty = tool.config_fields.filter((f) => !values[f]?.trim());
    if (empty.length > 0) {
      setError(`Missing required fields: ${empty.join(", ")}`);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSave(values);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Configuration failed"
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-md bg-zinc-900 border border-zinc-700 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-zinc-200">
            Configure {tool.name}
          </h3>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-zinc-500">{tool.description}</p>

        {error && (
          <div className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded text-xs text-red-400">
            {error}
          </div>
        )}

        <div className="space-y-3">
          {tool.config_fields.map((field) => (
            <div key={field}>
              <label className="block text-xs font-medium text-zinc-500 mb-1">
                {field.replace(/_/g, " ").replace(/\b\w/g, (c) =>
                  c.toUpperCase()
                )}
              </label>
              <input
                type={field.includes("key") || field.includes("password") || field.includes("token") ? "password" : "text"}
                value={values[field] ?? ""}
                onChange={(e) =>
                  setValues((prev) => ({
                    ...prev,
                    [field]: e.target.value,
                  }))
                }
                placeholder={`Enter ${field.replace(/_/g, " ")}`}
                className="w-full px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-lg text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
              />
            </div>
          ))}
        </div>

        <div className="flex items-center gap-2 pt-2">
          <button
            onClick={() => void handleSave()}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50"
          >
            <Check className="w-3 h-3" />
            {saving ? "Saving..." : "Save Configuration"}
          </button>
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-800 border border-zinc-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
