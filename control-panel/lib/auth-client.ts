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
export const authClient = createAuthClient({
  baseURL: process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000",
  plugins: [adminClient()],
});

export const { useSession, signIn, signOut } = authClient;
