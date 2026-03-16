/** API client for NEXUS backend.
 *
 * Browser-side calls go to the Next.js server which proxies to the
 * backend via Docker internal network. For direct browser access
 * (dev or exposed API), use the NEXT_PUBLIC_API_URL env var.
 */

import type { RegistryAgent } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

interface AgentListResponse {
  agents: RegistryAgent[];
}

interface AgentDetailResponse {
  agent: RegistryAgent;
}

interface AgentDeleteResponse {
  deleted: boolean;
  agent_id: string;
}

/** Fields for creating a new agent manually. */
export interface CreateAgentPayload {
  name: string;
  description: string;
  instructions?: string;
  role?: string;
  include_todo?: boolean;
  include_filesystem?: boolean;
  include_subagents?: boolean;
  include_skills?: boolean;
  include_memory?: boolean;
  include_web?: boolean;
  context_manager?: boolean;
  token_limit?: number | null;
  cost_budget_usd?: number | null;
}

interface AgentCreateResponse {
  agent: RegistryAgent;
  agent_id: string;
}

/** Create a new agent manually (no LLM builder). */
export async function createAgent(
  payload: CreateAgentPayload
): Promise<RegistryAgent> {
  const res = await fetch(`${API_BASE}/api/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Failed to create agent: ${res.status}`);
  }
  const data: AgentCreateResponse = await res.json();
  return data.agent;
}

/** Fetch all saved agents from the registry. */
export async function fetchAgents(): Promise<RegistryAgent[]> {
  const res = await fetch(`${API_BASE}/api/agents`);
  if (!res.ok) {
    throw new Error(`Failed to fetch agents: ${res.status}`);
  }
  const data: AgentListResponse = await res.json();
  return data.agents;
}

/** Update an agent's configuration (partial update). */
export async function updateAgent(
  agentId: string,
  updates: Partial<RegistryAgent>
): Promise<RegistryAgent> {
  const res = await fetch(`${API_BASE}/api/agents/${agentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    throw new Error(`Failed to update agent: ${res.status}`);
  }
  const data: AgentDetailResponse = await res.json();
  return data.agent;
}

/** Delete an agent from the registry. */
export async function deleteAgent(agentId: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/agents/${agentId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`Failed to delete agent: ${res.status}`);
  }
  const data: AgentDeleteResponse = await res.json();
  return data.deleted;
}
