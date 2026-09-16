import { apiFetch } from "./api";

// ---------------------------------------------------------------------------
// Agent roster
// ---------------------------------------------------------------------------

export interface AgentInfo {
  node: string;
  role: string;
  model: string | null;
  /** "store" when an operator override wins, else the routing.py default. */
  model_source?: "store" | "default" | string;
  /** Effective generation params ({} = code defaults). */
  params?: Record<string, number>;
  /** False skips the node's model call (the skip is recorded, never silent). */
  enabled?: boolean;
  /** Store-overridden fields, e.g. ["model", "params"]. */
  overridden?: string[];
  /** Stable prompt key for the four prompted nodes, else null. */
  prompt_key?: string | null;
  /** Effective prompt version (base + override hash). */
  prompt_version?: string | null;
  has_prompt_override?: boolean;
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
  return patchAgentConfig(node, { cap_usd: capUsd, cost_impact_note: costImpactNote });
}

// ---------------------------------------------------------------------------
// Model catalog (PBI-040) + full config patch (PBI-041)
// ---------------------------------------------------------------------------

export interface CatalogModel {
  id: string;
  name: string;
  context_length: number | null;
  prompt_price_per_m: number | null;
  completion_price_per_m: number | null;
  input_modalities: string[];
}

export interface CatalogList {
  models: CatalogModel[];
  stale: boolean;
  unavailable: boolean;
}

export interface AgentConfigPatch {
  cap_usd?: number | null;
  model?: string | null;
  params?: Record<string, number> | null;
  enabled?: boolean | null;
  prompt_override?: string | null;
  cost_impact_note: string;
}

/** Fetch the model catalog for the picker. `q` filters on id/name. */
export async function fetchModels(q?: string): Promise<CatalogList> {
  const path = q && q.trim() ? `/api/agents/models?q=${encodeURIComponent(q.trim())}` : "/api/agents/models";
  return apiFetch<CatalogList>(path);
}

/** Update a node's runtime config (cap, model, params, enabled). Admin-only. */
export async function patchAgentConfig(node: string, patch: AgentConfigPatch): Promise<AgentInfo> {
  return apiFetch<AgentInfo>(`/api/agents/${node}/config`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export interface PromptMeta {
  node: string;
  prompt_key: string | null;
  base_version: string | null;
  prompt_version: string | null;
  has_override: boolean;
  override_chars: number;
}

/** Prompt key/version/override presence (Viewer+). Text never travels. */
export async function fetchPromptMeta(node: string): Promise<PromptMeta> {
  return apiFetch<PromptMeta>(`/api/agents/${node}/prompt`);
}
