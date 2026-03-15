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

/** Agent record from the registry (PostgreSQL). */
export interface RegistryAgent {
  id: string;
  name: string;
  description: string;
  instructions: string;
  role: string;
  include_todo: boolean;
  include_filesystem: boolean;
  include_subagents: boolean;
  include_skills: boolean;
  include_memory: boolean;
  include_web: boolean;
  context_manager: boolean;
  token_limit: number | null;
  cost_budget_usd: number | null;
  status: string;
  total_runs: number;
  total_tokens: number;
  created_at: string;
  last_run_at: string | null;
}
