"use client";

import { useEffect, useState } from "react";

import { OverviewChart } from "@/components/analytics/analytics-view";
import { apiFetch } from "@/lib/api";
import type { OverviewResponse } from "@/lib/analytics";

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void apiFetch<OverviewResponse>("/api/analytics/overview")
      .then((data) => setOverview(data))
      .catch((err: unknown) => setError(String(err)));
  }, []);

  if (error) {
    return (
      <p className="border border-destructive p-4 font-mono text-xs text-destructive">
        Failed to load analytics: {error}
      </p>
    );
  }
  if (!overview) {
    return <p className="font-mono text-xs text-muted-foreground">Loading analytics…</p>;
  }
  return <OverviewChart overview={overview} />;
}
