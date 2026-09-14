"use client";

import { use, useEffect, useState } from "react";

import { KpiSeriesTable, RetirementBanner } from "@/components/analytics/analytics-view";
import { apiFetch } from "@/lib/api";
import type { CollectionKpiResponse, RetirementRecommendation } from "@/lib/analytics";

export default function CollectionAnalyticsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [kpi, setKpi] = useState<CollectionKpiResponse | null>(null);
  const [rec, setRec] = useState<RetirementRecommendation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void apiFetch<CollectionKpiResponse>(`/api/analytics/collections/${id}`)
      .then((data) => setKpi(data))
      .catch((err: unknown) => setError(String(err)));
    void apiFetch<RetirementRecommendation>(`/api/analytics/collections/${id}/recommendation`)
      .then((data) => setRec(data))
      .catch(() => {});
  }, [id]);

  if (error) {
    return (
      <p className="border border-destructive p-4 font-mono text-xs text-destructive">
        Failed to load KPI: {error}
      </p>
    );
  }
  if (!kpi) {
    return <p className="font-mono text-xs text-muted-foreground">Loading KPI…</p>;
  }

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-sm uppercase tracking-widest text-primary">{id} — KPI Dashboard</h1>
      {rec && <RetirementBanner rec={rec} />}
      <KpiSeriesTable kpi={kpi} />
      <p className="font-mono text-[11px] text-muted-foreground">
        Thresholds: min_units={kpi.kpi.thresholds.min_units ?? "—"} · eval_window={kpi.kpi.thresholds.eval_window_days ?? "—"}d
      </p>
    </div>
  );
}
