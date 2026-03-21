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
  const {
    messages,
    currentText,
    currentToolCalls,
    status,
    pendingApprovals,
  } = useNexusStore();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentText, currentToolCalls]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || status === "running") return;
    send(input.trim());
    setInput("");
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-emerald-900/40 text-emerald-100"
                  : "bg-zinc-800 text-zinc-200"
              }`}
            >
              <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
              {msg.toolCalls?.map((tc) => (
                <ToolCallBlock key={tc.id} toolCall={tc} />
              ))}
            </div>
          </div>
        ))}

        {/* Streaming content */}
        {(currentText || currentToolCalls.length > 0) && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-4 py-2 text-sm bg-zinc-800 text-zinc-200">
              {currentToolCalls.map((tc) => (
                <ToolCallBlock key={tc.id} toolCall={tc} />
              ))}
              {currentText && (
                <pre className="whitespace-pre-wrap font-sans">{currentText}</pre>
              )}
              {status === "running" && (
                <span className="inline-block w-2 h-4 bg-emerald-400 animate-pulse ml-0.5" />
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
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-600"
            disabled={status === "running"}
          />
          {status === "running" ? (
            <button
              type="button"
              onClick={cancel}
              className="px-4 py-2 bg-red-900/60 text-red-200 rounded-lg text-sm hover:bg-red-900/80"
            >
              Cancel
            </button>
          ) : (
            <button
              type="submit"
              className="px-4 py-2 bg-emerald-900/60 text-emerald-200 rounded-lg text-sm hover:bg-emerald-900/80"
            >
              Send
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
