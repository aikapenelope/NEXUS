import { useCallback, useRef } from "react";
import { useNexusStore } from "@/stores/nexus";
import type { AgentEvent } from "@/stores/nexus";

const WS_URL =
  typeof window !== "undefined"
    ? `ws://${window.location.hostname}:8000/ws/agent`
    : "ws://localhost:8000/ws/agent";

/** Fresh store access -- avoids stale closure issues. */
const gs = () => useNexusStore.getState();

export function useAgentStream() {
  const wsRef = useRef<WebSocket | null>(null);

  const send = useCallback((message: string) => {
    gs().addUserMessage(message);

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

      switch (event.type) {
        case "session_created":
          gs().setSessionId(event.session_id ?? null);
          break;
        case "start":
          gs().setStatus("running");
          break;
        case "text_delta":
          gs().appendTextDelta(event.content ?? "");
          break;
        case "tool_call_start":
          gs().addToolCall(
            event.tool_call_id ?? crypto.randomUUID(),
            event.tool_name ?? "unknown",
          );
          break;
        case "tool_args_delta":
          gs().appendToolArgs(event.args_delta ?? "");
          break;
        case "tool_start":
          break;
        case "tool_output":
          gs().setToolOutput(
            event.tool_name ?? "unknown",
            event.output ?? "",
          );
          break;
        case "todos_update":
          if (event.todos) gs().setTodos(event.todos);
          break;
        case "approval_required":
          if (event.requests) gs().setPendingApprovals(event.requests);
          break;
        case "response":
          gs().finalizeAssistantMessage(event.content ?? "");
          if (event.tokens_used) {
            useNexusStore.setState({
              tokensUsed: event.tokens_used,
              costUsd: event.cost_usd ?? 0,
            });
          }
          break;
        case "done":
          gs().setStatus("done");
          ws.close();
          break;
        case "error":
          gs().finalizeAssistantMessage(
            `Error: ${event.content ?? "Unknown error"}`,
          );
          gs().setStatus("error");
          ws.close();
          break;
        case "cancelled":
          gs().setStatus("done");
          ws.close();
          break;
      }
    };

    ws.onerror = () => {
      gs().setStatus("error");
    };
  }, []);

  const approve = useCallback((toolCallId: string, approved: boolean) => {
    wsRef.current?.send(
      JSON.stringify({ approval: { [toolCallId]: approved } }),
    );
    gs().setStatus("running");
  }, []);

  const cancel = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ cancel: true }));
  }, []);

  return { send, approve, cancel };
}
