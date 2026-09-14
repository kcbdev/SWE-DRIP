/** Catalog UI types + pure helpers (PBI-030; data via the catalog mirror API). */

export type InvariantStatus = "pass" | "fail" | "unmapped" | "unknown";

export interface CatalogItem {
  id: string;
  title: string | null;
  status: string | null;
  category: string | null;
  price: number | null;
  invariant: { status: InvariantStatus; expected: number | null; actual: number | null; reason: string | null };
  survivor_of: string | null;
}

export function badgeLabel(item: CatalogItem): string {
  const inv = item.invariant;
  if (inv.status === "pass") return "invariant pass";
  if (inv.status === "fail") return `invariant fail (expected $${inv.expected})`;
  return inv.reason ?? inv.status;
}
