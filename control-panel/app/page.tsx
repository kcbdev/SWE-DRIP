"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { DashboardView } from "@/components/dashboard/dashboard-view";
import { apiFetch } from "@/lib/api";
import type { DashboardSummary } from "@/lib/dashboard";

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DashboardSummary>("/api/dashboard/summary")
      .then(setSummary)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "failed to load dashboard")
      );
  }, []);

  return (
    <AppShell>
      <div className="flex flex-col gap-8">
        <header className="flex flex-col gap-1 border-b border-border pb-4">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-primary">SWE Drip</p>
          <h1 className="font-sans text-3xl font-semibold">Dashboard</h1>
        </header>
        <DashboardView summary={summary} error={error} />
      </div>
    </AppShell>
  );
}
