"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { RunsList } from "@/components/runs/runs-list";
import { apiFetch } from "@/lib/api";
import type { RunRow } from "@/lib/runs";

export default function RunsPage() {
  const [items, setItems] = useState<RunRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ items: RunRow[] }>("/api/runs")
      .then((body) => setItems(body.items))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "load failed"));
  }, []);

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <h1 className="font-sans text-2xl font-semibold">Runs</h1>
        {error ? <p className="font-mono text-xs text-destructive">{error}</p> : null}
        <RunsList items={items} />
      </div>
    </AppShell>
  );
}
