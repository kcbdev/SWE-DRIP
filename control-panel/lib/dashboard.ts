export interface SpendSummary {
  spend_usd: number;
  cap_usd: number;
  pct: number;
  warning: boolean;
  call_count: number;
}

export interface CollectionItem {
  slug?: string | null;
  name?: string | null;
  at_risk: boolean;
}

export interface CollectionsSummary {
  count: number;
  at_risk: boolean;
  items: CollectionItem[];
}

export interface ActivityItem {
  action: string;
  entity_type: string;
  entity_id?: string | null;
  actor: string;
  created_at: string;
}

export interface PendingItem {
  id?: string;
  type?: string;
  collection?: string;
  waiting_since?: string;
}

export interface DashboardSummary {
  pending_approvals: { count: number | null; items: PendingItem[] };
  spend: SpendSummary | null;
  collections: CollectionsSummary | null;
  activity: ActivityItem[] | null;
  sources: Record<string, "ok" | "unavailable">;
}

/** Human-relative timestamp for the activity feed (pure). */
export function relativeTime(iso: string, now: number = Date.now()): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return iso;
  const seconds = Math.max(0, Math.floor((now - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** Spend as an integer percentage of the cap (pure). */
export function spendPercent(spend: SpendSummary): number {
  return Math.round(spend.pct * 100);
}

export function formatUsd(value: number): string {
  return `$${value.toFixed(2)}`;
}
