"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { CatalogGrid } from "@/components/catalog/catalog-grid";
import { apiFetch } from "@/lib/api";
import type { CatalogItem } from "@/lib/catalog";

export default function CatalogPage() {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [source, setSource] = useState<string>("live");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ items: CatalogItem[]; source: string; error: string | null }>("/api/catalog")
      .then((body) => {
        setItems(body.items);
        setSource(body.source);
        setError(body.error);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "load failed"));
  }, []);

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <h1 className="font-sans text-2xl font-semibold">Catalog</h1>
        {source === "unavailable" || error ? (
          <p className="border border-destructive p-3 font-mono text-xs text-destructive">
            Fourthwall reads degraded: {error ?? "mirror unavailable"} — showing no cached data (mirrors are
            never fabricated).
          </p>
        ) : null}
        <CatalogGrid items={items} />
      </div>
    </AppShell>
  );
}
