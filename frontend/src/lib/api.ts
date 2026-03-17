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

// ── Workflow types ──────────────────────────────────────────────────

export interface WorkflowStep {
  agent_name: string;
  prompt_template: string;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  steps: WorkflowStep[];
  status: string;
  total_runs: number;
  created_at: string;
  last_run_at: string | null;
}

export interface CreateWorkflowPayload {
  name: string;
  description: string;
  steps: WorkflowStep[];
}

interface WorkflowListResponse {
  workflows: Workflow[];
}

interface WorkflowCreateResponse {
  workflow: Workflow;
}

interface WorkflowDeleteResponse {
  deleted: boolean;
  workflow_id: string;
}

export interface WorkflowRunResult {
  workflow_id: string;
  workflow_name: string;
  steps: {
    step: number;
    agent_name: string;
    agent_id: string;
    prompt: string;
    output: string;
    latency_ms: number;
    tokens: number;
  }[];
  final_output: string;
  total_steps: number;
}

// ── Workflow API functions ───────────────────────────────────────────

/** Fetch all workflows. */
export async function fetchWorkflows(): Promise<Workflow[]> {
  const res = await fetch(`${API_BASE}/api/workflows`);
  if (!res.ok) {
    throw new Error(`Failed to fetch workflows: ${res.status}`);
  }
  const data: WorkflowListResponse = await res.json();
  return data.workflows;
}

/** Create a new workflow. */
export async function createWorkflow(
  payload: CreateWorkflowPayload
): Promise<Workflow> {
  const res = await fetch(`${API_BASE}/api/workflows`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Failed to create workflow: ${res.status}`);
  }
  const data: WorkflowCreateResponse = await res.json();
  return data.workflow;
}

/** Delete a workflow. */
export async function deleteWorkflow(workflowId: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/workflows/${workflowId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`Failed to delete workflow: ${res.status}`);
  }
  const data: WorkflowDeleteResponse = await res.json();
  return data.deleted;
}

/** Run a workflow with an initial input. */
export async function runWorkflow(
  workflowId: string,
  input: string
): Promise<WorkflowRunResult> {
  const res = await fetch(`${API_BASE}/api/workflows/${workflowId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });
  if (!res.ok) {
    throw new Error(`Failed to run workflow: ${res.status}`);
  }
  return res.json();
}
