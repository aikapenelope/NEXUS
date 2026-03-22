"use client";

import { useState, useRef, useEffect } from "react";
import { useNexusStore } from "@/stores/nexus";
import { useAgentStream } from "@/hooks/useAgentStream";
import { ToolCallBlock } from "./ToolCallBlock";
import { ApprovalModal } from "./ApprovalModal";

export function ChatPanel() {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { send, cancel } = useAgentStream();
  const messages = useNexusStore((s) => s.messages);
  const currentText = useNexusStore((s) => s.currentText);
  const currentToolCalls = useNexusStore((s) => s.currentToolCalls);
  const status = useNexusStore((s) => s.status);
  const pendingApprovals = useNexusStore((s) => s.pendingApprovals);
  const sessionId = useNexusStore((s) => s.sessionId);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentText, currentToolCalls]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || status === "running") return;
    send(input.trim());
    setInput("");
  };

  const isStreaming =
    status === "running" &&
    (currentText.length > 0 || currentToolCalls.length > 0);

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !isStreaming && (
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
        {(status === "running" || currentToolCalls.length > 0) && (
          <div className="flex justify-start">
            <div className="max-w-[85%] rounded-lg px-4 py-3 text-sm bg-zinc-800/80 text-zinc-200 border border-zinc-700/40">
              {currentToolCalls.length > 0 && (
                <div className="mb-2">
                  {currentToolCalls.map((tc) => (
                    <ToolCallBlock key={tc.id} toolCall={tc} />
                  ))}
                </div>
              )}
              {currentText && (
                <pre className="whitespace-pre-wrap font-sans leading-relaxed">
                  {currentText}
                </pre>
              )}
              {status === "running" && (
                <span className="inline-block w-1.5 h-4 bg-emerald-400 animate-pulse ml-0.5 align-middle" />
              )}
            </div>
          </div>
        )}

        {/* Approval modal */}
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
              onClick={cancel}
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
        {sessionId && (
          <p className="text-[10px] text-zinc-600 mt-1.5 px-1">
            session: {sessionId.slice(0, 16)}...
          </p>
        )}
      </form>
    </div>
  );
}
