"use client";

import { CopilotChat } from "@copilotkit/react-ui";
import { useCoAgent } from "@copilotkit/react-core";
import { Sidebar } from "@/components/Sidebar";
import { RightPanel } from "@/components/RightPanel";
import { StateRenderers } from "@/components/generative-ui/StateRenderers";
import type { NexusState } from "@/lib/types";

export default function Home() {
  const { state } = useCoAgent<NexusState>({
    name: "nexus_copilot",
    initialState: {
      current_agent: {
        name: "",
        role: "",
        model: "",
        tools: [],
        status: "idle" as const,
      },
      cerebro_stages: [],
      memories: [],
      active_panel: "chat",
      last_agent_config: {},
    },
  });

  return (
    <div className="flex h-screen bg-zinc-950">
      {/* Generative UI state renderers (invisible — inject components into chat) */}
      <StateRenderers />

      {/* Left sidebar */}
      <Sidebar activePanel={state?.active_panel ?? "chat"} />

      {/* Center: Chat */}
      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-12 flex items-center px-4 border-b border-zinc-800">
          <h1 className="text-sm font-medium text-zinc-300">NEXUS</h1>
          <span className="ml-2 text-xs text-zinc-500">v0.4.0</span>
        </header>
        <div className="flex-1 overflow-hidden">
          <CopilotChat
            className="copilotKitChat h-full"
            labels={{
              title: "NEXUS Agent Platform",
              initial: "Hello! I'm NEXUS. I can build AI agents, run analysis pipelines, and manage semantic memory. What would you like to do?",
              placeholder: "Ask NEXUS to build an agent, run Cerebro, or search memory...",
            }}
          />
        </div>
      </main>

      {/* Right panel */}
      <RightPanel state={state} />
    </div>
  );
}
