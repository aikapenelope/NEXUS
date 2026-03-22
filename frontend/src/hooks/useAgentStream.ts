import { useCallback, useRef } from "react";
import { useNexusStore } from "@/stores/nexus";
import type { AgentEvent } from "@/stores/nexus";

const WS_URL =
  typeof window !== "undefined"
    ? `ws://${window.location.hostname}:8000/ws/agent`
    : "ws://localhost:8000/ws/agent";

export function useAgentStream() {
  const wsRef = useRef<WebSocket | null>(null);

  const send = useCallback((message: string) => {
    const state = useNexusStore.getState();
    state.addUserMessage(message);

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      const s = useNexusStore.getState();
      ws.send(
        JSON.stringify({
          message,
          agent: s.agent,
          session_id: s.sessionId,
        }),
      );
    };

    ws.onmessage = (e: MessageEvent) => {
      const event: AgentEvent = JSON.parse(e.data as string);
      const s = useNexusStore.getState();

      switch (event.type) {
        case "session_created":
          s.setSessionId(event.session_id ?? null);
          break;
        case "start":
          s.setStatus("running");
          break;
        case "text_delta":
          s.appendTextDelta(event.content ?? "");
          break;
        case "tool_call_start":
          s.addToolCall(
            event.tool_call_id ?? crypto.randomUUID(),
            event.tool_name ?? "unknown",
          );
          break;
        case "tool_args_delta":
          s.appendToolArgs(event.args_delta ?? "");
          break;
        case "tool_start":
          // tool_start fires AFTER tool_call_start for the same tool.
          // Don't create a duplicate -- just update args if needed.
          break;
        case "tool_output":
          s.setToolOutput(
            event.tool_name ?? "unknown",
            event.output ?? "",
          );
          break;
        case "todos_update":
          if (event.todos) s.setTodos(event.todos);
          break;
        case "approval_required":
          if (event.requests) s.setPendingApprovals(event.requests);
          break;
        case "response":
          s.finalizeAssistantMessage(event.content ?? "");
          if (event.tokens_used) {
            useNexusStore.setState({
              tokensUsed: event.tokens_used,
              costUsd: event.cost_usd ?? 0,
            });
          }
          break;
        case "done":
          s.setStatus("done");
          ws.close();
          break;
        case "error":
          s.finalizeAssistantMessage(
            `Error: ${event.content ?? "Unknown error"}`,
          );
          s.setStatus("error");
          ws.close();
          break;
        case "cancelled":
          s.setStatus("done");
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
