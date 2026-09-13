import { Pool } from "pg";

/**
 * Audit writer for the Control Panel side (Better Auth auth events).
 *
 * Uses the same `audit_log` schema as the FastAPI writer — see
 * `api/migrations/0001_audit_log.sql`. Append-only: this module only INSERTs.
 * The connection pool is constructed lazily; no query runs until an event fires.
 */
const pool = new Pool({ connectionString: process.env.DATABASE_URL });

export const SYSTEM_ACTOR = "system";

export interface AuditEntry {
  actorUserId: string;
  action: string;
  entityType: string;
  entityId?: string | null;
  before?: unknown;
  after?: unknown;
}

export async function writeAudit(entry: AuditEntry): Promise<void> {
  if (!entry.actorUserId) {
    throw new Error("actorUserId is required; use SYSTEM_ACTOR explicitly");
  }
  await pool.query(
    `INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, before_json, after_json)
     VALUES ($1, $2, $3, $4, $5, $6)`,
    [
      entry.actorUserId,
      entry.action,
      entry.entityType,
      entry.entityId ?? null,
      entry.before === undefined ? null : JSON.stringify(entry.before),
      entry.after === undefined ? null : JSON.stringify(entry.after),
    ]
  );
}

/** Map a Better Auth request path to an audit action (pure, testable). */
export function authEventForPath(
  path: string
): { action: string; entityType: string } | null {
  if (path === "/sign-in/email") return { action: "auth.login", entityType: "session" };
  if (path === "/sign-out") return { action: "auth.logout", entityType: "session" };
  return null;
}
