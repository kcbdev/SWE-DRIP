import { betterAuth } from "better-auth";
import { createAuthMiddleware } from "better-auth/api";
import { admin } from "better-auth/plugins";
import { Pool } from "pg";

import { SYSTEM_ACTOR, authEventForPath, writeAudit } from "./audit";

/**
 * Better Auth is the single auth runtime (spec C1). It owns credential storage
 * and session lifecycle in the shared Postgres; FastAPI only validates the
 * sessions it issues. Public signup is disabled — users are invited by an admin.
 *
 * The connection pool is constructed but not opened until a query runs, so
 * `next build` needs no database.
 */
export const auth = betterAuth({
  // Cross-origin API calls (panel origin -> api subdomain) only carry the
  // session cookie when it is scoped to the shared parent domain. Set
  // COOKIE_DOMAIN=.kcb.ma in production; leave unset for localhost dev.
  advanced: process.env.COOKIE_DOMAIN
    ? {
        crossSubDomainCookies: {
          enabled: true,
          domain: process.env.COOKIE_DOMAIN,
        },
      }
    : undefined,
  database: new Pool({ connectionString: process.env.DATABASE_URL }),
  secret: process.env.BETTER_AUTH_SECRET ?? "dev-only-secret-change-me",
  baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
  emailAndPassword: {
    enabled: true,
    disableSignUp: true,
  },
  session: {
    expiresIn: 60 * 60 * 24,
    updateAge: 60 * 60,
  },
  plugins: [
    admin({
      defaultRole: "viewer",
      adminRoles: ["admin"],
    }),
  ],
  hooks: {
    // Auth events are written to the shared audit_log table (spec C4). Failures
    // never block authentication; the event is best-effort from the hook.
    // NOTE: the hook MUST be wrapped in createAuthMiddleware — a raw async
    // function returns undefined and crashes better-auth's after-hook runner
    // (`result.headers` of undefined).
    after: createAuthMiddleware(async (ctx: any) => {
      const event = authEventForPath(ctx?.path ?? "");
      if (!event) return;
      const session = ctx?.context?.newSession;
      await writeAudit({
        actorUserId: session?.userId ?? SYSTEM_ACTOR,
        action: event.action,
        entityType: event.entityType,
        entityId: session?.id ?? null,
      }).catch(() => undefined);
    }),
  },
});
