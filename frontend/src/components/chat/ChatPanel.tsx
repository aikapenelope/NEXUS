"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useNexusStore } from "@/stores/nexus";
import type { AgentEvent, ToolCall } from "@/stores/nexus";
import { ToolCallBlock } from "./ToolCallBlock";
import { ApprovalModal } from "./ApprovalModal";

const WS_URL =
  typeof window !== "undefined"
    ? `ws://${window.location.hostname}:8000/ws/agent`
    : "ws://localhost:8000/ws/agent";

interface Message {
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
}

/**
 * ChatPanel with direct DOM-style state management for WebSocket events.
 * Uses local React state (useState) instead of zustand for streaming,
 * avoiding the batching issues that caused tool calls to disappear.
 */
export function ChatPanel() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamText, setStreamText] = useState("");
  const [streamTools, setStreamTools] = useState<ToolCall[]>([]);
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [tokensUsed, setTokensUsed] = useState(0);
  const [costUsd, setCostUsd] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const toolsRef = useRef<ToolCall[]>([]);

  const agent = useNexusStore((s) => s.agent);
  const pendingApprovals = useNexusStore((s) => s.pendingApprovals);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamText, streamTools]);

  const handleSend = useCallback(
    (message: string) => {
      if (!message.trim() || status === "running") return;

      // Add user message
      setMessages((prev) => [...prev, { role: "user", content: message }]);
      setStreamText("");
      setStreamTools([]);
      setStatus("running");
      toolsRef.current = [];

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ message, agent, session_id: sessionId }));
      };

      ws.onmessage = (e: MessageEvent) => {
        const event: AgentEvent = JSON.parse(e.data as string);

        switch (event.type) {
          case "session_created":
            setSessionId(event.session_id ?? null);
            break;

          case "start":
            setStatus("running");
            toolsRef.current = [];
            break;

          case "text_delta":
            setStreamText((prev) => prev + (event.content ?? ""));
            break;

          case "tool_call_start": {
            const tc: ToolCall = {
              id: event.tool_call_id ?? Math.random().toString(36).slice(2),
              name: event.tool_name ?? "unknown",
              args: "",
              status: "running",
            };
            toolsRef.current = [...toolsRef.current, tc];
            setStreamTools([...toolsRef.current]);
            console.log("[NEXUS] tool_call_start", tc.name, "ref:", toolsRef.current.length);
            break;
          }

          case "tool_args_delta": {
            const ref = toolsRef.current;
            if (ref.length > 0) {
              const last = ref[ref.length - 1];
              toolsRef.current = [
                ...ref.slice(0, -1),
                { ...last, args: last.args + (event.args_delta ?? "") },
              ];
              setStreamTools([...toolsRef.current]);
            }
            break;
          }

          case "tool_start":
            // Already handled by tool_call_start
            break;

          case "tool_output": {
            const name = event.tool_name ?? "unknown";
            toolsRef.current = toolsRef.current.map((tc) =>
              tc.name === name
                ? { ...tc, output: event.output ?? "", status: "done" }
                : tc,
            );
            setStreamTools([...toolsRef.current]);
            break;
          }

          case "todos_update":
            if (event.todos) {
              useNexusStore.getState().setTodos(event.todos);
            }
            break;

          case "approval_required":
            if (event.requests) {
              useNexusStore.getState().setPendingApprovals(event.requests);
            }
            break;

          case "response": {
            // Finalize: move streaming content to messages
            const finalTools = toolsRef.current.map((tc) => ({
              ...tc,
              status: "done" as const,
            }));
            const content = event.content ?? "";

            console.log("[NEXUS] response, toolsRef:", toolsRef.current.length, "finalTools:", finalTools.length);

            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content,
                toolCalls: finalTools.length > 0 ? finalTools : undefined,
              },
            ]);
            setStreamText("");
            setStreamTools([]);
            setStatus("done");
            toolsRef.current = [];

            if (event.tokens_used) {
              setTokensUsed(event.tokens_used);
              setCostUsd(event.cost_usd ?? 0);
            }
            break;
          }

          case "done":
            setStatus("done");
            ws.close();
            break;

          case "error":
            setMessages((prev) => [
              ...prev,
              { role: "assistant", content: `Error: ${event.content ?? "Unknown"}` },
            ]);
            setStatus("error");
            toolsRef.current = [];
            ws.close();
            break;

          case "cancelled":
            setStatus("done");
            toolsRef.current = [];
            ws.close();
            break;
        }
      };

      ws.onerror = () => setStatus("error");
    },
    [agent, sessionId, status],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend(input.trim());
    setInput("");
  };

  const handleCancel = () => {
    wsRef.current?.send(JSON.stringify({ cancel: true }));
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && streamTools.length === 0 && !streamText && (
          <div className="text-center text-zinc-600 mt-20">
            <p className="text-lg font-medium text-zinc-400">NEXUS</p>
            <p className="text-sm mt-1">
              Self-hosted coding agent. Ask me to write, fix, or analyze code.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-4 py-3 text-sm ${
                msg.role === "user"
                  ? "bg-emerald-900/30 text-emerald-100 border border-emerald-800/40"
                  : "bg-zinc-800/80 text-zinc-200 border border-zinc-700/40"
              }`}
            >
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div className="mb-2">
                  {msg.toolCalls.map((tc) => (
                    <ToolCallBlock key={tc.id} toolCall={tc} />
                  ))}
                </div>
              )}
              <pre className="whitespace-pre-wrap font-sans leading-relaxed">
                {msg.content}
              </pre>
            </div>
          </div>
        ))}

        {/* Streaming content */}
        {(streamTools.length > 0 || streamText) && (
          <div className="flex justify-start">
            <div className="max-w-[85%] rounded-lg px-4 py-3 text-sm bg-zinc-800/80 text-zinc-200 border border-zinc-700/40">
              {streamTools.map((tc) => (
                <ToolCallBlock key={tc.id} toolCall={tc} />
              ))}
              {streamText && (
                <pre className="whitespace-pre-wrap font-sans leading-relaxed">
                  {streamText}
                </pre>
              )}
              {status === "running" && (
                <span className="inline-block w-1.5 h-4 bg-emerald-400 animate-pulse ml-0.5 align-middle" />
              )}
            </div>
          </div>
        )}

        {pendingApprovals.length > 0 && <ApprovalModal />}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-zinc-800">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask NEXUS to code, fix, or analyze..."
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600/30"
            disabled={status === "running"}
          />
          {status === "running" ? (
            <button
              type="button"
              onClick={handleCancel}
              className="px-4 py-2.5 bg-red-900/50 text-red-200 rounded-lg text-sm hover:bg-red-900/70 transition-colors"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="px-4 py-2.5 bg-emerald-800/60 text-emerald-200 rounded-lg text-sm hover:bg-emerald-800/80 transition-colors disabled:opacity-40"
            >
              Send
            </button>
          )}
        </div>
        <div className="flex items-center gap-3 mt-1.5 px-1 text-[10px] text-zinc-600">
          {sessionId && <span>session: {sessionId.slice(0, 12)}</span>}
          {tokensUsed > 0 && (
            <>
              <span className="text-emerald-600">
                {tokensUsed.toLocaleString()} tokens
              </span>
              <span className="text-emerald-600">${costUsd.toFixed(4)}</span>
            </>
          )}
        </div>
      </form>
    </div>
  );
}
