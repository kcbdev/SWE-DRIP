/**
 * Dev auth bypass parsing (PBI-057) — local UI verification only.
 *
 * Pure and unit-tested; mirrors api/app/dev_bypass.py. The bypass email is
 * NEVER a NEXT_PUBLIC_ variable: only server code (middleware, the dev
 * session route) reads it. Client components learn the *role* through the
 * auth-client wrapper, never the flag.
 */

export const DEV_BYPASS_ENV = "SWE_DRIP_DEV_AUTH_BYPASS";

/** Parse the bypass env value: email string, or null when off. Throws on garbage. */
export function devBypassEmail(raw: string | undefined): string | null {
  const value = (raw ?? "").trim();
  if (!value || value.toLowerCase() === "false") return null;
  const parts = value.split("@");
  if (parts.length !== 2 || !parts[0] || !parts[1] || /\s/.test(value)) {
    throw new Error(
      `${DEV_BYPASS_ENV} must be empty, 'false', or an email — got ${JSON.stringify(value)}`,
    );
  }
  return value;
}

/** Production refuses the bypass (defense in depth; the API hard-refuses to boot). */
export function isProductionEnv(appEnv: string | undefined): boolean {
  return (appEnv ?? "").trim().toLowerCase() === "production";
}

/**
 * Middleware decision (pure): redirect to /login only when the page is
 * gated, no session cookie is present, and no dev bypass applies.
 */
export function shouldRedirectToLogin(
  pathname: string,
  hasSession: boolean,
  isPublic: boolean,
  bypassEmail: string | null,
): boolean {
  if (isPublic) return false;
  if (hasSession) return false;
  if (bypassEmail) return false;
  void pathname;
  return true;
}
