/** Runs UI types + pure helpers (PBI-029; data via the PBI-028 API). */

export const NODE_ORDER = [
  "trend_research",
  "contract_approval",
  "listing_copy",
  "design_spec",
  "art_render",
  "placement",
  "aesthetic_qc",
  "technical_qc",
  "fw_create",
  "publish_gate",
  "shelf",
] as const;

export type NodeName = (typeof NODE_ORDER)[number];

export interface RunRow {
  id: string;
  collection_id: string | null;
  design_id: string | null;
  status: string;
  current_node: string | null;
  started_at: string | null;
  updated_at: string | null;
}

export interface NodePanel {
  node: string;
  reached: boolean;
  state: unknown;
  at: string | null;
}

export interface NodeConfigSummary {
  model: string | null;
  params: Record<string, number>;
  enabled: boolean;
}

export interface RunDetail extends RunRow {
  nodes: NodePanel[];
  /** Trimmed per-node runtime config (model/params/enabled) so a run explains itself. */
  node_config?: Record<string, NodeConfigSummary>;
  errors: string[];
}

export interface LogRow {
  node: string;
  level: string;
  message: string;
  detail: Record<string, unknown>;
  ts: string;
}

export type TrackerState = "complete" | "current" | "pending" | "failed";

/** Tracker states along the locked order; current = furthest reached node. */
export function trackerStates(detail: RunDetail): { node: string; state: TrackerState }[] {
  const reached = new Set(detail.nodes.filter((n) => n.reached).map((n) => n.node));
  const furthest = Math.max(-1, ...detail.nodes.map((n, i) => (n.reached ? i : -1)));
  return detail.nodes.map((n, i) => ({
    node: n.node,
    state: !reached.has(n.node)
      ? "pending"
      : detail.status === "failed" && i === furthest
        ? "failed"
        : i === furthest
          ? "current"
          : "complete",
  }));
}

export type FlowState = "complete" | "current" | "awaiting-approval" | "failed" | "not-reached";

/**
 * Status-coloured flow states (PBI-042, spec C8): like trackerStates, but the
 * furthest reached node reflects an awaiting gate, and unreached nodes are
 * explicitly "not-reached" rather than "pending".
 */
export function flowStates(detail: RunDetail): { node: string; state: FlowState }[] {
  const reached = new Set(detail.nodes.filter((n) => n.reached).map((n) => n.node));
  const furthest = Math.max(-1, ...detail.nodes.map((n, i) => (n.reached ? i : -1)));
  return detail.nodes.map((n, i) => {
    if (!reached.has(n.node)) return { node: n.node, state: "not-reached" as FlowState };
    if (i !== furthest) return { node: n.node, state: "complete" as FlowState };
    if (detail.status === "awaiting_approval") return { node: n.node, state: "awaiting-approval" as FlowState };
    if (detail.status === "failed") return { node: n.node, state: "failed" as FlowState };
    return { node: n.node, state: "current" as FlowState };
  });
}

/**
 * Per-node durations in seconds from log timestamps (first → last row).
 * Null when a node has fewer than two timestamped rows — durations are
 * observed, never synthesized.
 */
export function nodeDurations(logs: LogRow[]): Record<string, number | null> {
  const byNode = new Map<string, number[]>();
  for (const row of logs) {
    const ts = Date.parse(row.ts);
    if (Number.isNaN(ts)) continue;
    const list = byNode.get(row.node) ?? [];
    list.push(ts);
    byNode.set(row.node, list);
  }
  const out: Record<string, number | null> = {};
  for (const [node, stamps] of byNode) {
    out[node] = stamps.length >= 2 ? (Math.max(...stamps) - Math.min(...stamps)) / 1000 : null;
  }
  return out;
}

/** Human-readable duration: 0.5s, 12s, 3m 04s. */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

/** The API must return exactly the locked node set — else a loud mismatch warning. */
export function nodeSetMismatch(nodes: NodePanel[]): string[] {
  const got = nodes.map((n) => n.node);
  const missing = NODE_ORDER.filter((n) => !got.includes(n));
  const extra = got.filter((n) => !(NODE_ORDER as readonly string[]).includes(n));
  return [...missing.map((n) => `missing: ${n}`), ...extra.map((n) => `extra: ${n}`)];
}

/** Readable JSON for node panels (same conventions as the audit diff viewer). */
export function prettyState(state: unknown): string {
  if (state === null || state === undefined) return "—";
  return JSON.stringify(state, null, 2);
}
