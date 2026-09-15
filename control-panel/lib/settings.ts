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
// Integrations
// ---------------------------------------------------------------------------

export interface IntegrationsStatus {
  /** Fourthwall Open API username + password both present. */
  fourthwall: boolean;
  /** OpenRouter API key present. */
  openrouter: boolean;
  /** Non-secret endpoint hint. */
  fourthwall_base_url: string;
  /** Non-secret identifier (the API user name). */
  fourthwall_username: string;
  /** Non-secret endpoint hint. */
  openrouter_base_url: string;
}

export interface IntegrationsPatch {
  fourthwall_api_base_url?: string;
  fourthwall_api_username?: string;
  /** Write-only: never returned by the API. Empty string clears it. */
  fourthwall_api_password?: string;
  /** Write-only: never returned by the API. Empty string clears it. */
  openrouter_api_key?: string;
  openrouter_base_url?: string;
}

export interface IntegrationTestResult {
  ok: boolean;
  error?: string;
  products_seen?: number;
}

/** Fetch integration presence + non-secret endpoints (never secret values). */
export async function fetchIntegrations(): Promise<IntegrationsStatus> {
  return apiFetch<IntegrationsStatus>("/api/settings/integrations");
}

/** Set integration credentials. Admin-only; confirmation required. */
export async function saveIntegrations(
  patch: IntegrationsPatch,
): Promise<IntegrationsStatus> {
  return apiFetch<IntegrationsStatus>("/api/settings/integrations", {
    method: "PATCH",
    body: JSON.stringify({ ...patch, confirm: true }),
  });
}

/** Probe the configured Fourthwall API. Admin-only; degraded read is not an error. */
export async function testFourthwall(): Promise<IntegrationTestResult> {
  return apiFetch<IntegrationTestResult>("/api/settings/integrations/test", {
    method: "POST",
  });
}
