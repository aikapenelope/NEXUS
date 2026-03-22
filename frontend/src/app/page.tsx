"use client";

import { ChatPanel } from "@/components/chat/ChatPanel";
import { AgentSelector } from "@/components/sidebar/AgentSelector";
import { TodoProgress } from "@/components/panels/TodoProgress";
import { RightPanel } from "@/components/panels/RightPanel";
import { StatusBar } from "@/components/StatusBar";

export default function Home() {
  return (
    <div className="flex flex-col h-screen bg-zinc-950">
      <div className="flex flex-1 min-h-0">
        {/* Left sidebar */}
        <aside className="w-56 border-r border-zinc-800 flex flex-col">
          <div className="h-12 flex items-center px-4 border-b border-zinc-800">
            <h1 className="text-sm font-bold text-zinc-200">NEXUS</h1>
            <span className="ml-2 text-[10px] text-zinc-600">v0.5.0</span>
          </div>
          <AgentSelector />
          <div className="flex-1" />
          <TodoProgress />
        </aside>

        {/* Center: Chat */}
        <main className="flex-1 flex flex-col min-w-0">
          <div className="h-12 flex items-center px-4 border-b border-zinc-800">
            <span className="text-xs text-zinc-400">Chat</span>
          </div>
          <div className="flex-1 min-h-0">
            <ChatPanel />
          </div>
        </main>

        {/* Right panel */}
        <RightPanel />
      </div>

      <StatusBar />
    </div>
  );
}
