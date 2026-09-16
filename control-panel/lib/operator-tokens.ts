import { apiFetch } from "./api";

// ---------------------------------------------------------------------------
// Operator tokens (PBI-043 API; metadata only — values never travel except
// once, inside the issuance response).
// ---------------------------------------------------------------------------

export type TokenScope = "read" | "operate";

export interface OperatorToken {
  id: number;
  prefix: string;
  name: string;
  scopes: TokenScope[];
  created_by: string;
  revoked: boolean;
  last_used_at: string | null;
  created_at: string;
}

export interface IssuedToken extends OperatorToken {
  /** Shown exactly once at issuance. Never stored, never refetched. */
  token: string;
}

/** List token metadata (Admin-only; hashes/values never leave the store). */
export async function fetchTokens(): Promise<OperatorToken[]> {
  const body = await apiFetch<{ items: OperatorToken[] }>("/api/operator-tokens");
  return body.items;
}

/** Issue a token. Admin-only; audited server-side with prefix only. */
export async function issueToken(name: string, scopes: TokenScope[]): Promise<IssuedToken> {
  return apiFetch<IssuedToken>("/api/operator-tokens", {
    method: "POST",
    body: JSON.stringify({ name, scopes }),
  });
}

/** Flag a token revoked (Admin-only, audited, idempotent-safe read of 409). */
export async function revokeToken(id: number): Promise<{ id: number; prefix: string; revoked: boolean }> {
  return apiFetch(`/api/operator-tokens/${id}/revoke`, { method: "POST" });
}

/** Public MCP endpoint URL for client configs (same host as the API). */
export function mcpEndpointUrl(): string {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");
  return `${base || "https://swedrip-api.kcb.ma"}/mcp/`;
}

/** Copy text to the clipboard; false when the API is unavailable. */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
