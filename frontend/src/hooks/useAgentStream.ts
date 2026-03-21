import { useCallback, useRef } from "react";
import { useNexusStore } from "@/stores/nexus";
import type { AgentEvent } from "@/stores/nexus";

const WS_URL =
  typeof window !== "undefined"
    ? `ws://${window.location.hostname}:8000/ws/agent`
    : "ws://localhost:8000/ws/agent";

export function useAgentStream() {
  const wsRef = useRef<WebSocket | null>(null);
  const store = useNexusStore();

  const send = useCallback(
    (message: string) => {
      store.addUserMessage(message);

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            message,
            agent: store.agent,
            session_id: store.sessionId,
          }),
        );
      };

      ws.onmessage = (e: MessageEvent) => {
        const event: AgentEvent = JSON.parse(e.data as string);

        switch (event.type) {
          case "session_created":
            store.setSessionId(event.session_id ?? null);
            break;
          case "start":
            store.setStatus("running");
            break;
          case "text_delta":
            store.appendTextDelta(event.content ?? "");
            break;
          case "tool_call_start":
            store.addToolCall(
              event.tool_call_id ?? crypto.randomUUID(),
              event.tool_name ?? "unknown",
            );
            break;
          case "tool_args_delta":
            store.appendToolArgs(event.args_delta ?? "");
            break;
          case "tool_start":
            store.addToolCall(
              event.tool_call_id ?? crypto.randomUUID(),
              event.tool_name ?? "unknown",
            );
            break;
          case "tool_output":
            store.setToolOutput(
              event.tool_name ?? "unknown",
              event.output ?? "",
            );
            break;
          case "todos_update":
            if (event.todos) store.setTodos(event.todos);
            break;
          case "approval_required":
            if (event.requests) store.setPendingApprovals(event.requests);
            break;
          case "response":
            store.finalizeAssistantMessage(event.content ?? "");
            break;
          case "done":
            store.setStatus("done");
            ws.close();
            break;
          case "error":
            store.finalizeAssistantMessage(`Error: ${event.content ?? "Unknown error"}`);
            store.setStatus("error");
            ws.close();
            break;
          case "cancelled":
            store.setStatus("done");
            ws.close();
            break;
        }
      };

      ws.onerror = () => {
        store.setStatus("error");
      };
    },
    [store],
  );

  const approve = useCallback(
    (toolCallId: string, approved: boolean) => {
      wsRef.current?.send(
        JSON.stringify({ approval: { [toolCallId]: approved } }),
      );
      store.setStatus("running");
    },
    [store],
  );

  const cancel = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ cancel: true }));
  }, []);

  return { send, approve, cancel };
}
