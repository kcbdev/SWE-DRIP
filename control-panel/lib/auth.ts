import { betterAuth } from "better-auth";
import { admin } from "better-auth/plugins";
import { Pool } from "pg";

/**
 * Better Auth is the single auth runtime (spec C1). It owns credential storage
 * and session lifecycle in the shared Postgres; FastAPI only validates the
 * sessions it issues. Public signup is disabled — users are invited by an admin.
 *
 * The connection pool is constructed but not opened until a query runs, so
 * `next build` needs no database.
 */
export const auth = betterAuth({
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
});
