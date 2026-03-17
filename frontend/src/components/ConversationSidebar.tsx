"use client";

/**
 * ConversationSidebar: collapsible panel listing chat conversations
 * grouped by date (Today, Yesterday, Previous 7 days, Older).
 *
 * Sits between the icon Sidebar and the main chat area, following
 * the ChatGPT/Claude sidebar pattern.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { Plus, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchConversations,
  createConversationApi,
  deleteConversationApi,
  type Conversation,
} from "@/lib/api";

interface ConversationSidebarProps {
  /** Currently selected conversation ID (null = new chat). */
  activeId: string | null;
  /** Called when user selects a conversation or creates a new one. */
  onSelect: (id: string | null) => void;
  /** External signal to refresh the list (incremented after message save). */
  refreshKey?: number;
}

// ── Date grouping helpers ───────────────────────────────────────────

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

interface GroupedConversations {
  label: string;
  items: Conversation[];
}

function groupByDate(conversations: Conversation[]): GroupedConversations[] {
  const now = new Date();
  const todayStart = startOfDay(now);
  const yesterdayStart = todayStart - 86_400_000;
  const weekStart = todayStart - 7 * 86_400_000;

  const groups: Record<string, Conversation[]> = {
    Today: [],
    Yesterday: [],
    "Previous 7 days": [],
    Older: [],
  };

  for (const c of conversations) {
    const t = new Date(c.updated_at).getTime();
    if (t >= todayStart) groups["Today"].push(c);
    else if (t >= yesterdayStart) groups["Yesterday"].push(c);
    else if (t >= weekStart) groups["Previous 7 days"].push(c);
    else groups["Older"].push(c);
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }));
}

// ── Component ───────────────────────────────────────────────────────

export function ConversationSidebar({
  activeId,
  onSelect,
  refreshKey = 0,
}: ConversationSidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Fetch conversations on mount and when refreshKey changes.
  // We store the loader in a ref so the effect body itself doesn't
  // call setState synchronously (satisfies react-hooks/immutability).
  const loadConversations = useCallback(async () => {
    try {
      const data = await fetchConversations();
      setConversations(data);
    } catch {
      // Silently fail — sidebar is non-critical
    }
  }, []);

  const loaderRef = useRef(loadConversations);
  useEffect(() => {
    loaderRef.current = loadConversations;
  }, [loadConversations]);

  useEffect(() => {
    void loaderRef.current();
  }, [refreshKey]);

  const handleNewChat = async () => {
    try {
      const conv = await createConversationApi();
      setConversations((prev) => [conv, ...prev]);
      onSelect(conv.id);
    } catch {
      // Fallback: just clear the chat
      onSelect(null);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteConversationApi(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) {
        onSelect(null);
      }
    } catch {
      // Silently fail
    }
    setDeleteConfirm(null);
  };

  const grouped = groupByDate(conversations);

  // Collapsed state: thin strip with toggle button
  if (collapsed) {
    return (
      <div className="w-8 flex flex-col items-center py-4 border-r border-zinc-800 bg-zinc-950/50">
        <button
          onClick={() => setCollapsed(false)}
          title="Expand conversations"
          className="w-6 h-6 rounded flex items-center justify-center text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <aside className="w-64 flex flex-col border-r border-zinc-800 bg-zinc-950/50">
      {/* Header */}
      <div className="h-12 flex items-center justify-between px-3 border-b border-zinc-800">
        <button
          onClick={handleNewChat}
          className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>
        <button
          onClick={() => setCollapsed(true)}
          title="Collapse sidebar"
          className="w-6 h-6 rounded flex items-center justify-center text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto py-2 px-2">
        {conversations.length === 0 && (
          <p className="text-xs text-zinc-600 px-2 py-4 text-center">
            No conversations yet
          </p>
        )}

        {grouped.map((group) => (
          <div key={group.label} className="mb-3">
            <h3 className="text-[10px] font-medium text-zinc-600 uppercase tracking-wider px-2 mb-1">
              {group.label}
            </h3>
            {group.items.map((conv) => (
              <div
                key={conv.id}
                className={cn(
                  "group flex items-center gap-1 rounded-lg px-2 py-1.5 cursor-pointer transition-colors",
                  activeId === conv.id
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-300"
                )}
                onClick={() => onSelect(conv.id)}
              >
                <span className="flex-1 text-xs truncate">
                  {conv.title || "New conversation"}
                </span>

                {/* Delete button */}
                {deleteConfirm === conv.id ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(conv.id);
                    }}
                    className="text-red-400 hover:text-red-300 text-[10px] font-medium shrink-0"
                  >
                    Confirm
                  </button>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteConfirm(conv.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 text-zinc-600 hover:text-red-400 transition-opacity shrink-0"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </aside>
  );
}
