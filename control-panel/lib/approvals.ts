/** Approvals queue types + pure helpers (PBI-018; data via the PBI-016 API). */

export type DecisionAction = "approve" | "reject" | "regenerate";

export type ApprovalTab = "all" | "collections" | "designs" | "publishes";

export interface EntityRef {
  type: string;
  id: string | null;
  label: string;
}

export interface ApprovalItem {
  id: number;
  run_id: string;
  node: string;
  status: string;
  payload: Record<string, unknown>;
  entity_ref: EntityRef;
  waiting_since: string | null;
  clusters?: { cluster_id?: string }[];
  reviewer_user_id?: string | null;
  note?: string | null;
}

export interface DecisionResult {
  id: number;
  run_id: string;
  node: string;
  action: DecisionAction;
  status: string;
  resumed: boolean;
}

const NODE_TO_TAB: Record<string, ApprovalTab> = {
  contract_approval: "collections",
  aesthetic_qc: "designs",
  publish_gate: "publishes",
};

export const TABS: { key: ApprovalTab; label: string }[] = [
  { key: "all", label: "All" },
  { key: "collections", label: "Collections" },
  { key: "designs", label: "Designs" },
  { key: "publishes", label: "Publishes" },
];

export function tabFor(item: ApprovalItem): ApprovalTab {
  return NODE_TO_TAB[item.node] ?? "all";
}

export function filterByTab(items: ApprovalItem[], tab: ApprovalTab): ApprovalItem[] {
  if (tab === "all") return items;
  return items.filter((item) => tabFor(item) === tab);
}

/** Human waiting age from an ISO timestamp ("12m", "3h", "2d", "—"). Pure. */
export function waitingAge(iso: string | null, nowMs: number = Date.now()): string {
  if (!iso) return "—";
  const diffMs = nowMs - new Date(iso).getTime();
  if (Number.isNaN(diffMs) || diffMs < 0) return "—";
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "<1m";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

/**
 * Detail route for a queue item where one exists, else null.
 * Collection gates deep-link to the Collections screen (PBI-021); design and
 * run detail routes land with PBI-024 / PBI-029.
 */
export function detailHrefFor(item: ApprovalItem): string | null {
  if (item.entity_ref.type === "collection_contract" && item.entity_ref.id) {
    return `/collections/${item.entity_ref.id}`;
  }
  if (item.node === "aesthetic_qc") {
    return `/designs/${item.run_id}`;
  }
  return null;
}

/** Reject requires a non-empty note (feeds regeneration). */
export function rejectNoteValid(note: string): boolean {
  return note.trim().length > 0;
}
