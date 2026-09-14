"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import type { Calibration } from "@/lib/designs";

export default function DesignsPage() {
  const [items, setItems] = useState<Calibration[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ items: Calibration[] }>("/api/calibration")
      .then((body) => setItems(body.items))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "load failed"));
  }, []);

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <h1 className="font-sans text-2xl font-semibold">Design QC</h1>
        {error ? <p className="font-mono text-xs text-destructive">{error}</p> : null}
        {items.length === 0 ? (
          <p className="border border-border p-4 font-mono text-xs text-muted-foreground">
            No designs with QC state.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {items.map((item) => (
              <li key={item.run_id} className="border border-border bg-card p-3">
                <Link href={`/designs/${item.run_id}`} className="font-mono text-sm text-primary">
                  {item.design_id ?? item.run_id}
                </Link>
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  rubric: {item.rubric.result ?? "unknown"} ·{" "}
                  {item.agreement === null ? "no human decision yet" : `agreement: ${item.agreement}`}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  );
}
