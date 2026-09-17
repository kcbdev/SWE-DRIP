/** Collections UI types + pure helpers (PBI-021; data via the PBI-019/020 API). */

export type CollectionStatus = "draft" | "active" | "retired";

export type CollectionFilter = "all" | CollectionStatus;

export interface CollectionContract {
  collection_id: string;
  theme: string;
  status: CollectionStatus;
  style_archetype: string;
  illustration_rules: { line_weight: string | null; palette: string[]; no_mixed_styles: boolean };
  garment_colorways: { base: string; contrast_pass: boolean }[];
  placement_templates: { design_type: string; front: string; back: string; sleeve: string }[];
  product_count_target: number | null;
  lifecycle_days: number | null;
  kpi_thresholds: { min_units: number | null; min_conversion: number | null; eval_window_days: number | null };
  created_by: string;
  created_at: string;
  approved_at: string | null;
  retired_at: string | null;
  survivor_products?: string[];
  slug?: string;
  // V2 visual direction (collection-research spec C2, PBI-048): all optional
  // so v1 contracts keep validating; the research view renders them.
  style_descriptors?: string[];
  mood_board?: string[];
  inspiration_refs?: { url: string; note: string }[];
  avoid?: string[];
  board_version?: number;
}

export interface CollectionRecord {
  id: string;
  contract: CollectionContract;
  mtime: number;
}

export const FILTERS: { key: CollectionFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "active", label: "Active" },
  { key: "draft", label: "Candidates" },
  { key: "retired", label: "Retired" },
];

export function filterCollections(items: CollectionRecord[], filter: CollectionFilter) {
  return filter === "all" ? items : items.filter((i) => i.contract.status === filter);
}

/** Days left in the lifecycle window from approval (null when not computable). */
export function lifecycleDaysLeft(contract: CollectionContract, nowMs: number = Date.now()): number | null {
  if (contract.status !== "active" || !contract.approved_at || !contract.lifecycle_days) return null;
  const approved = new Date(contract.approved_at).getTime();
  if (Number.isNaN(approved)) return null;
  const elapsed = Math.floor((nowMs - approved) / 86400000);
  return Math.max(0, contract.lifecycle_days - elapsed);
}

/** Client-side required-field check before POST (server re-validates). */
export function creationErrors(input: { collection_id: string; theme: string }): string[] {
  const errors: string[] = [];
  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(input.collection_id)) {
    errors.push("collection_id must be lowercase kebab-case");
  }
  if (!input.theme.trim()) errors.push("theme is required");
  return errors;
}

/** Parse a comma-separated survivor list into product ids. */
export function parseSurvivors(raw: string): string[] {
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
}
