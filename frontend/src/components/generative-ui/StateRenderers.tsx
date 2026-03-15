"use client";

import { useCoAgentStateRender } from "@copilotkit/react-core";
import { AgentCard } from "./AgentCard";
import { CerebroPipelineView } from "./CerebroPipelineView";
import { MemoryList } from "./MemoryList";
import type { NexusState } from "@/lib/types";

/**
 * Registers Generative UI renderers that inject components into the
 * CopilotChat stream based on the shared NexusState.
 *
 * This component renders nothing visible itself — it only registers
 * the useCoAgentStateRender hooks that CopilotKit uses to render
 * inline UI in the chat when agent state changes.
 */
export function StateRenderers() {
  // Render AgentCard when an agent is being built or is ready
  useCoAgentStateRender<NexusState>({
    name: "nexus_copilot",
    render: ({ state }) => {
      if (!state?.current_agent?.name) return null;
      return <AgentCard agent={state.current_agent} />;
    },
  });

  // Render CerebroPipelineView when Cerebro stages are active
  useCoAgentStateRender<NexusState>({
    name: "nexus_copilot",
    render: ({ state }) => {
      if (!state?.cerebro_stages?.length) return null;
      return <CerebroPipelineView stages={state.cerebro_stages} />;
    },
  });

  // Render MemoryList when memories are loaded
  useCoAgentStateRender<NexusState>({
    name: "nexus_copilot",
    render: ({ state }) => {
      if (!state?.memories?.length) return null;
      return <MemoryList memories={state.memories} />;
    },
  });

  return null;
}
