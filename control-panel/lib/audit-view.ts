export interface AuditQueryParams {
  actor?: string;
  action?: string;
  entity_type?: string;
  entity_id?: string;
  start?: string;
  end?: string;
  limit?: number;
}

export interface AuditEntry {
  id: number | string;
  actor_user_id: string;
  created_at: string;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  before_json?: unknown;
  after_json?: unknown;
}

/** Build the `GET /api/audit` query string from UI filters (pure). */
export function buildAuditQuery(params: AuditQueryParams): string {
  const query = new URLSearchParams();
  if (params.actor) query.set("actor", params.actor);
  if (params.action) query.set("action", params.action);
  if (params.entity_type) query.set("entity_type", params.entity_type);
  if (params.entity_id) query.set("entity_id", params.entity_id);
  if (params.start) query.set("start", params.start);
  if (params.end) query.set("end", params.end);
  if (params.limit) query.set("limit", String(params.limit));
  return query.toString();
}

/** Render a `before → after` diff cell (pure). */
export function formatDiff(before: unknown, after: unknown): string {
  const left = before === undefined || before === null ? "—" : JSON.stringify(before);
  const right = after === undefined || after === null ? "—" : JSON.stringify(after);
  return `${left} → ${right}`;
}
