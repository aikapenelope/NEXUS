/** Shared state types mirroring the Python NexusState dataclass. */

export interface AgentInfo {
  name: string;
  role: string;
  model: string;
  tools: string[];
  status: "idle" | "building" | "ready" | "running" | "completed";
}

export interface CerebroStage {
  name: string;
  status: "pending" | "running" | "completed";
  output: string;
}

export interface MemoryEntry {
  id: string;
  memory: string;
  score: number;
}

export interface NexusState {
  current_agent: AgentInfo;
  cerebro_stages: CerebroStage[];
  memories: MemoryEntry[];
  active_panel: string;
  last_agent_config: Record<string, unknown>;
}
