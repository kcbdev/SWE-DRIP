"use client";

import Link from "next/link";

import { formatRevenue, kpiBadgeColor, type CollectionKpiResponse, type OverviewResponse } from "@/lib/analytics";

export function OverviewChart({ overview }: { overview: OverviewResponse }) {
  return (
    <div className="space-y-3">
      <h2 className="font-mono text-sm uppercase tracking-widest text-primary">Revenue Overview</h2>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="border border-border bg-card p-4">
          <p className="font-mono text-xs text-muted-foreground">Revenue (12m)</p>
          <p className="mt-1 font-mono text-lg text-foreground">{formatRevenue(overview.revenue_12m)}</p>
        </div>
        <div className="border border-border bg-card p-4">
          <p className="font-mono text-xs text-muted-foreground">Units (12m)</p>
          <p className="mt-1 font-mono text-lg text-foreground">{overview.units_12m}</p>
        </div>
        <div className="border border-border bg-card p-4">
          <p className="font-mono text-xs text-muted-foreground">Break-even</p>
          <p className={`mt-1 font-mono text-lg ${overview.above_break_even ? "text-primary" : "text-destructive"}`}>
            {formatRevenue(overview.break_even)} {overview.above_break_even ? "✓" : "✗"}
          </p>
        </div>
      </div>
    </div>
  );
}

export function CollectionKpiCard({ kpi }: { kpi: CollectionKpiResponse }) {
  return (
    <li className="border border-border bg-card p-3">
      <Link href={`/analytics/${kpi.collection_id}`} className="font-mono text-sm text-primary">
        {kpi.collection_id}
      </Link>
      <p className="mt-1 font-mono text-xs text-muted-foreground">
        {kpi.summary.units_in_eval_window} units in eval window · {formatRevenue(kpi.summary.revenue_in_eval_window)}
      </p>
      <div className="mt-2 flex gap-4">
        {kpi.kpi.series.map((pt) => (
          <div key={pt.window_days} className="text-center">
            <p className="font-mono text-[10px] text-muted-foreground">{pt.window_days}d</p>
            <p className={`font-mono text-xs ${kpiBadgeColor(pt.passes_min_units)}`}>{pt.units}</p>
          </div>
        ))}
      </div>
      <p className={`mt-1 font-mono text-xs ${kpi.summary.below_min_units ? "text-destructive" : "text-primary"}`}>
        {kpi.summary.below_min_units ? "below threshold" : "threshold met"}
      </p>
    </li>
  );
}

export function KpiSeriesTable({ kpi }: { kpi: CollectionKpiResponse }) {
  return (
    <table className="w-full font-mono text-xs">
      <thead>
        <tr className="border-b border-border">
          <th className="py-1 text-left text-muted-foreground">Window</th>
          <th className="py-1 text-right text-muted-foreground">Units</th>
          <th className="py-1 text-right text-muted-foreground">Revenue</th>
          <th className="py-1 text-right text-muted-foreground">Min Units</th>
        </tr>
      </thead>
      <tbody>
        {kpi.kpi.series.map((pt) => (
          <tr key={pt.window_days} className="border-b border-border/50">
            <td className="py-1">{pt.window_days} days</td>
            <td className={`py-1 text-right ${kpiBadgeColor(pt.passes_min_units)}`}>{pt.units}</td>
            <td className="py-1 text-right">{formatRevenue(pt.revenue)}</td>
            <td className="py-1 text-right text-muted-foreground">{kpi.kpi.thresholds.min_units ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function RetirementBanner({ rec }: { rec: { verdict: string; reason: string; collection_id: string } }) {
  if (rec.verdict !== "retirement_recommended") return null;
  return (
    <div className="border border-destructive bg-destructive/10 p-4">
      <p className="font-mono text-xs text-destructive">Retirement recommended for {rec.collection_id}</p>
      <p className="mt-1 font-mono text-[11px] text-muted-foreground">{rec.reason}</p>
      <Link href={`/collections/${rec.collection_id}`} className="mt-2 inline-block font-mono text-xs text-primary hover:underline">
        → View in Collections
      </Link>
    </div>
  );
}
