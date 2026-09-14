"use client";

import { use, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import { badgeLabel, type CatalogItem } from "@/lib/catalog";

interface OrderRow {
  id: string;
  status?: string | null;
  total?: number | null;
}

interface CatalogDetail extends CatalogItem {
  order_history: OrderRow[];
  order_history_scope: string;
}

export default function CatalogDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [item, setItem] = useState<CatalogDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<CatalogDetail>(`/api/catalog/${id}`)
      .then(setItem)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "load failed"));
  }, [id]);

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <h1 className="font-sans text-2xl font-semibold">{item?.title ?? "Product"}</h1>
        {error ? <p className="font-mono text-xs text-destructive">{error}</p> : null}
        {item ? (
          <>
            <dl className="grid grid-cols-2 gap-2 border border-border bg-card p-4 font-mono text-xs">
              <dt className="text-muted-foreground">id</dt>
              <dd>{item.id}</dd>
              <dt className="text-muted-foreground">status</dt>
              <dd>{item.status ?? "unknown"}</dd>
              <dt className="text-muted-foreground">price</dt>
              <dd>{item.price !== null ? `$${item.price}` : "no price"}</dd>
              <dt className="text-muted-foreground">invariant</dt>
              <dd className={item.invariant.status === "pass" ? "text-primary" : "text-destructive"}>
                {badgeLabel(item)}
              </dd>
              {item.survivor_of ? (
                <>
                  <dt className="text-muted-foreground">survivor</dt>
                  <dd className="text-primary">live via {item.survivor_of} exception</dd>
                </>
              ) : null}
            </dl>
            <div className="border border-border p-4">
              <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
                Order history ({item.order_history_scope})
              </p>
              {item.order_history.length === 0 ? (
                <p className="mt-2 font-mono text-xs text-muted-foreground">no orders recorded</p>
              ) : (
                <ul className="mt-2 font-mono text-xs">
                  {item.order_history.map((order) => (
                    <li key={order.id}>
                      {order.id} · {order.status ?? "?"} · {order.total ?? "?"}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        ) : (
          <p className="font-mono text-xs text-muted-foreground">{error ?? "Loading…"}</p>
        )}
      </div>
    </AppShell>
  );
}
