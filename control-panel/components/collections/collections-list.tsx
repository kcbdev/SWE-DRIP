"use client";

import Link from "next/link";

import { FILTERS, filterCollections, type CollectionFilter, type CollectionRecord } from "@/lib/collections";
import { useState } from "react";

export function CollectionsList({
  items,
  canCreate,
}: {
  items: CollectionRecord[];
  canCreate: boolean;
}) {
  const [filter, setFilter] = useState<CollectionFilter>("all");
  const visible = filterCollections(items, filter);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            aria-pressed={filter === f.key}
            className={`border px-3 py-1 font-mono text-xs uppercase tracking-widest ${
              filter === f.key ? "border-primary text-primary" : "border-border text-muted-foreground"
            }`}
          >
            {f.label}
          </button>
        ))}
        {canCreate ? (
          <Link
            href="/collections/new"
            className="ml-auto border border-primary px-3 py-1 font-mono text-xs text-primary"
          >
            New collection
          </Link>
        ) : null}
      </div>

      {visible.length === 0 ? (
        <p className="border border-border p-4 font-mono text-xs text-muted-foreground">
          No collections{filter === "all" ? "" : ` with status ${filter}`}.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {visible.map((item) => (
            <li key={item.id} className="border border-border bg-card p-3">
              <Link href={`/collections/${item.id}`} className="font-mono text-sm text-primary">
                {item.contract.theme}
              </Link>
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                {item.id} · {item.contract.status} · {item.contract.style_archetype}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
