/** Analytics UI types + pure helpers (PBI-031; data via the analytics API). */

export interface KpiThresholds {
  min_units: number | null;
  min_conversion: number | null;
  eval_window_days: number | null;
}

export interface KpiSeriesPoint {
  window_days: number;
  units: number;
  revenue: number;
  passes_min_units: boolean;
  passes_min_conversion: boolean;
}

export interface CollectionKpiResponse {
  collection_id: string;
  kpi: { series: KpiSeriesPoint[]; thresholds: KpiThresholds };
  summary: { units_in_eval_window: number; revenue_in_eval_window: number; below_min_units: boolean; below_min_conversion: boolean };
}

export interface RetirementRecommendation {
  collection_id: string;
  verdict: "retirement_recommended" | "no_recommendation";
  reason: string;
  units: number;
  revenue: number;
  min_units: number;
  eval_window_days: number;
  recommendation?: string;
  note: string;
}

export interface OverviewResponse {
  revenue_12m: number;
  units_12m: number;
  break_even: number;
  above_break_even: boolean;
  active_product_types: number;
}

export function formatRevenue(val: number): string {
  return `$${val.toFixed(2)}`;
}

export function kpiBadgeColor(passes: boolean): string {
  return passes ? "text-primary" : "text-destructive";
}
