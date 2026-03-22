import { create } from "zustand";

// ── Event types from WebSocket ──────────────────────────────────────

export type AgentEventType =
  | "session_created"
  | "start"
  | "text_delta"
  | "thinking_delta"
  | "tool_call_start"
  | "tool_args_delta"
  | "tool_start"
  | "tool_output"
  | "todos_update"
  | "approval_required"
  | "response"
  | "done"
  | "error"
  | "cancelled";

export interface AgentEvent {
  type: AgentEventType;
  content?: string;
  tool_name?: string;
  tool_call_id?: string;
  args?: Record<string, unknown> | string;
  args_delta?: string;
  output?: string;
  todos?: TodoItem[];
  requests?: ApprovalRequest[];
  session_id?: string;
  tokens_used?: number;
  cost_usd?: number;
}

export interface TodoItem {
  title: string;
  status: "pending" | "in_progress" | "completed";
}

export interface ApprovalRequest {
  tool_call_id: string;
  tool_name: string;
  args: Record<string, unknown> | string;
}

export interface ToolCall {
  id: string;
  name: string;
  args: string;
  output?: string;
  status: "running" | "done";
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
  timestamp: number;
}

export interface SessionInfo {
  id: string;
  agent: string;
  messageCount: number;
  createdAt: number;
}

// ── Store ───────────────────────────────────────────────────────────

interface NexusStore {
  // Session
  sessionId: string | null;
  agent: string;
  status: "idle" | "running" | "approval" | "done" | "error";

  // Messages
  messages: ChatMessage[];
  currentText: string;
  currentToolCalls: ToolCall[];

  // Todos
  todos: TodoItem[];

  // Approval
  pendingApprovals: ApprovalRequest[];

  // Stats
  tokensUsed: number;
  costUsd: number;

  // Sessions list
  sessions: SessionInfo[];

  // Actions
  setAgent: (agent: string) => void;
  setSessionId: (id: string | null) => void;
  setStatus: (status: NexusStore["status"]) => void;
  addUserMessage: (content: string) => void;
  appendTextDelta: (delta: string) => void;
  addToolCall: (id: string, name: string) => void;
  appendToolArgs: (delta: string) => void;
  setToolOutput: (name: string, output: string) => void;
  setTodos: (todos: TodoItem[]) => void;
  setPendingApprovals: (requests: ApprovalRequest[]) => void;
  finalizeAssistantMessage: (content: string) => void;
  reset: () => void;
  setSessions: (sessions: SessionInfo[]) => void;
}

export const useNexusStore = create<NexusStore>((set) => ({
  sessionId: null,
  agent: "nexus-developer",
  status: "idle",
  messages: [],
  currentText: "",
  currentToolCalls: [],
  todos: [],
  pendingApprovals: [],
  tokensUsed: 0,
  costUsd: 0,
  sessions: [],

  setAgent: (agent) => set({ agent }),
  setSessionId: (id) => set({ sessionId: id }),
  setStatus: (status) => set({ status }),

  addUserMessage: (content) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { role: "user", content, timestamp: Date.now() },
      ],
      currentText: "",
      currentToolCalls: [],
      status: "running",
    })),

  appendTextDelta: (delta) =>
    set((s) => ({ currentText: s.currentText + delta })),

  addToolCall: (id, name) =>
    set((s) => ({
      currentToolCalls: [
        ...s.currentToolCalls,
        { id, name, args: "", status: "running" },
      ],
    })),

  appendToolArgs: (delta) =>
    set((s) => {
      const calls = [...s.currentToolCalls];
      if (calls.length > 0) {
        calls[calls.length - 1] = {
          ...calls[calls.length - 1],
          args: calls[calls.length - 1].args + delta,
        };
      }
      return { currentToolCalls: calls };
    }),

  setToolOutput: (name, output) =>
    set((s) => ({
      currentToolCalls: s.currentToolCalls.map((tc) =>
        tc.name === name ? { ...tc, output, status: "done" } : tc,
      ),
    })),

  setTodos: (todos) => set({ todos }),
  setPendingApprovals: (requests) =>
    set({ pendingApprovals: requests, status: "approval" }),

  finalizeAssistantMessage: (content) =>
    set((s) => {
      // Preserve tool calls that happened during this turn
      const toolCalls =
        s.currentToolCalls.length > 0
          ? s.currentToolCalls.map((tc) => ({ ...tc, status: "done" as const }))
          : undefined;

      return {
        messages: [
          ...s.messages,
          {
            role: "assistant",
            content: content || s.currentText,
            toolCalls,
            timestamp: Date.now(),
          },
        ],
        currentText: "",
        currentToolCalls: [],
        status: "done",
      };
    }),

  reset: () =>
    set({
      sessionId: null,
      status: "idle",
      messages: [],
      currentText: "",
      currentToolCalls: [],
      todos: [],
      pendingApprovals: [],
      tokensUsed: 0,
    }),

  setSessions: (sessions) => set({ sessions }),
}));
