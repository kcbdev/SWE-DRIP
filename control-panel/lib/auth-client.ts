import { useEffect, useState } from "react";

import { createAuthClient } from "better-auth/react";
import { adminClient } from "better-auth/client/plugins";

/**
 * Better Auth browser client. Talks to the same-origin `/api/auth/*` routes
 * (dev: Next rewrite to FastAPI; prod: Traefik path routing). The session cookie
 * is first-party, so no token is ever held in JS.
 *
 * `adminClient` mirrors the server's `admin()` plugin, which is what lets an
 * admin actually create a user (Better Auth owns credential storage — the
 * FastAPI user store manages profile/role/activation only).
 */
const baseClient = createAuthClient({
  baseURL: process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000",
  plugins: [adminClient()],
});

interface DevIdentity {
  email: string;
  role: string;
}

/**
 * Merge a dev-bypass identity into a session result (pure — unit-tested).
 * The bypass only ever upgrades to what `/api/dev/session` asserts; a null
 * identity passes the real result through untouched.
 */
export function mergeDevSession<T extends { data: unknown; isPending: boolean }>(
  real: T,
  dev: DevIdentity | null,
): T {
  if (!dev) return real;
  const data = { ...((real.data as Record<string, unknown> | null) ?? {}) };
  const user = { ...((data.user as Record<string, unknown> | undefined) ?? {}) };
  const merged = {
    ...data,
    user: { ...user, email: dev.email, role: dev.role },
  };
  return { ...real, isPending: false, data: merged as T["data"] };
}

/**
 * `useSession` with dev-bypass support (PBI-057). When the dev bypass is
 * enabled server-side, `/api/dev/session` asserts an admin identity and the
 * hook synthesizes a session from it — every page calling
 * `authClient.useSession()` (or the exported `useSession`) sees an admin
 * without touching page code. When the bypass is off the real result passes
 * through byte-identically (the probe 401s and nothing changes).
 */
type SessionResult = ReturnType<typeof baseClient.useSession>;

function useSessionWithBypass(
  ...args: Parameters<typeof baseClient.useSession>
): SessionResult {
  const real = baseClient.useSession(...args);
  const [dev, setDev] = useState<DevIdentity | null>(null);
  // Probe only when there is no real session: logged-in users never hit
  // /api/dev/session (which 401s in production and spams the console),
  // while logged-out dev sessions still upgrade to the bypass identity.
  const needsProbe = !real.isPending && !real.data;
  useEffect(() => {
    if (!needsProbe) return;
    let live = true;
    fetch("/api/dev/session", { credentials: "same-origin" })
      .then(async (response) => {
        if (!live || !response.ok) return;
        const body = (await response.json()) as { email?: unknown; role?: unknown };
        if (typeof body.email === "string" && typeof body.role === "string") {
          setDev({ email: body.email, role: body.role });
        }
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [needsProbe]);
  return mergeDevSession(real, dev);
}

export const authClient = {
  ...baseClient,
  useSession: useSessionWithBypass,
};

export const { useSession, signIn, signOut } = authClient;
