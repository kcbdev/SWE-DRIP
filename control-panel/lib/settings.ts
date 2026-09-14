import { apiFetch, isAdmin } from "./api";

// ---------------------------------------------------------------------------
// HITL flags
// ---------------------------------------------------------------------------

export type HitlFlags = Record<string, boolean>;

/** Fetch per-node HITL toggle state. */
export async function fetchHitlFlags(): Promise<HitlFlags> {
  return apiFetch<HitlFlags>("/api/settings/hitl");
}

/** Toggle a single node's HITL flag. Admin-only; requires confirmation. */
export async function toggleHitl(node: string, enabled: boolean): Promise<HitlFlags> {
  return apiFetch<HitlFlags>("/api/settings/hitl", {
    method: "PATCH",
    body: JSON.stringify({ node, enabled, confirm: true }),
  });
}

// ---------------------------------------------------------------------------
// Brand-lock constants
// ---------------------------------------------------------------------------

export interface BrandConstants {
  palette: Record<string, string>;
  typeface: string;
  forbidden: string[];
}

/** Fetch brand-lock constants (palette, typeface, forbidden elements). */
export async function fetchBrand(): Promise<BrandConstants> {
  return apiFetch<BrandConstants>("/api/settings/brand");
}

/** Edit brand-lock constants. Admin-only; requires confirmation. */
export async function patchBrand(patch: Partial<BrandConstants>): Promise<BrandConstants> {
  return apiFetch<BrandConstants>("/api/settings/brand", {
    method: "PATCH",
    body: JSON.stringify({ ...patch, confirm: true }),
  });
}

// ---------------------------------------------------------------------------
// Integrations status
// ---------------------------------------------------------------------------

export interface IntegrationsStatus {
  fourthwall_mcp: boolean;
  openrouter_key: boolean;
}

/** Fetch integration presence status (booleans only, never secret values). */
export async function fetchIntegrations(): Promise<IntegrationsStatus> {
  return apiFetch<IntegrationsStatus>("/api/settings/integrations");
}
