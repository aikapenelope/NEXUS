import { useCallback, useRef } from "react";
import { useNexusStore } from "@/stores/nexus";
import type { AgentEvent, ToolCall } from "@/stores/nexus";

const WS_URL =
  typeof window !== "undefined"
    ? `ws://${window.location.hostname}:8000/ws/agent`
    : "ws://localhost:8000/ws/agent";

/**
 * WebSocket hook for agent streaming.
 *
 * Tool calls are accumulated in a ref (outside React render cycle)
 * to avoid state batching issues. They're synced to zustand for
 * real-time display AND preserved in the ref for finalizeAssistantMessage.
 */
export function useAgentStream() {
  const wsRef = useRef<WebSocket | null>(null);
  // Accumulate tool calls outside React state to survive batching
  const toolCallsRef = useRef<ToolCall[]>([]);

  const send = useCallback((message: string) => {
    const gs = useNexusStore.getState;
    gs().addUserMessage(message);
    toolCallsRef.current = [];

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          message,
          agent: gs().agent,
          session_id: gs().sessionId,
        }),
      );
    };

    ws.onmessage = (e: MessageEvent) => {
      const event: AgentEvent = JSON.parse(e.data as string);
      const gs = useNexusStore.getState;

      switch (event.type) {
        case "session_created":
          gs().setSessionId(event.session_id ?? null);
          break;

        case "start":
          gs().setStatus("running");
          toolCallsRef.current = [];
          break;

        case "text_delta":
          gs().appendTextDelta(event.content ?? "");
          break;

        case "tool_call_start": {
          const tc: ToolCall = {
            id: event.tool_call_id ?? crypto.randomUUID(),
            name: event.tool_name ?? "unknown",
            args: "",
            status: "running",
          };
          toolCallsRef.current = [...toolCallsRef.current, tc];
          gs().addToolCall(tc.id, tc.name);
          break;
        }

        case "tool_args_delta":
          // Update ref
          if (toolCallsRef.current.length > 0) {
            const last = toolCallsRef.current[toolCallsRef.current.length - 1];
            toolCallsRef.current = [
              ...toolCallsRef.current.slice(0, -1),
              { ...last, args: last.args + (event.args_delta ?? "") },
            ];
          }
          gs().appendToolArgs(event.args_delta ?? "");
          break;

        case "tool_start":
          // Already handled by tool_call_start
          break;

        case "tool_output": {
          const name = event.tool_name ?? "unknown";
          const output = event.output ?? "";
          toolCallsRef.current = toolCallsRef.current.map((tc) =>
            tc.name === name ? { ...tc, output, status: "done" } : tc,
          );
          gs().setToolOutput(name, output);
          break;
        }

        case "todos_update":
          if (event.todos) gs().setTodos(event.todos);
          break;

        case "approval_required":
          if (event.requests) gs().setPendingApprovals(event.requests);
          break;

        case "response": {
          // Use ref (guaranteed to have all tool calls) not zustand state
          const preserved = toolCallsRef.current.length > 0
            ? toolCallsRef.current.map((tc) => ({ ...tc, status: "done" as const }))
            : undefined;
          gs().finalizeWithToolCalls(event.content ?? "", preserved);
          if (event.tokens_used) {
            useNexusStore.setState({
              tokensUsed: event.tokens_used,
              costUsd: event.cost_usd ?? 0,
            });
          }
          toolCallsRef.current = [];
          break;
        }

        case "done":
          gs().setStatus("done");
          ws.close();
          break;

        case "error":
          gs().finalizeWithToolCalls(
            `Error: ${event.content ?? "Unknown error"}`,
            toolCallsRef.current.length > 0 ? [...toolCallsRef.current] : undefined,
          );
          gs().setStatus("error");
          toolCallsRef.current = [];
          ws.close();
          break;

        case "cancelled":
          gs().setStatus("done");
          toolCallsRef.current = [];
          ws.close();
          break;
      }
    };

    ws.onerror = () => {
      useNexusStore.getState().setStatus("error");
    };
  }, []);

  const approve = useCallback((toolCallId: string, approved: boolean) => {
    wsRef.current?.send(
      JSON.stringify({ approval: { [toolCallId]: approved } }),
    );
    useNexusStore.getState().setStatus("running");
  }, []);

  const cancel = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ cancel: true }));
  }, []);

  return { send, approve, cancel };
}
