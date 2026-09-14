import { apiFetch } from "./api";

// ---------------------------------------------------------------------------
// Agent roster
// ---------------------------------------------------------------------------

export interface AgentInfo {
  node: string;
  role: string;
  model: string | null;
  cap_usd: number;
  spend_usd: number;
  routing_edit: string;
}

/** Fetch the full agent roster. */
export async function fetchAgents(): Promise<AgentInfo[]> {
  return apiFetch<AgentInfo[]>("/api/agents");
}

/** Fetch a single agent's detail. */
export async function fetchAgentDetail(node: string): Promise<AgentInfo> {
  return apiFetch<AgentInfo>(`/api/agents/${node}`);
}

/** Update a node's budget cap. Admin-only; requires cost-impact note. */
export async function patchAgentCap(
  node: string,
  capUsd: number,
  costImpactNote: string,
): Promise<AgentInfo> {
  return apiFetch<AgentInfo>(`/api/agents/${node}/config`, {
    method: "PATCH",
    body: JSON.stringify({ cap_usd: capUsd, cost_impact_note: costImpactNote }),
  });
}
