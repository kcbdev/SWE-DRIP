import { createAuthClient } from "better-auth/react";

/**
 * Better Auth browser client. Talks to the same-origin `/api/auth/*` routes
 * (dev: Next rewrite to FastAPI; prod: Traefik path routing). The session cookie
 * is first-party, so no token is ever held in JS.
 */
export const authClient = createAuthClient({
  baseURL: process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000",
});

export const { useSession, signIn, signOut } = authClient;
