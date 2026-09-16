"use client";

import Link from "next/link";
import { useState } from "react";

import type { RunRow } from "@/lib/runs";

export function RunsList({ items }: { items: RunRow[] }) {
  const [search, setSearch] = useState("");
  const [collection, setCollection] = useState("");
  const [status, setStatus] = useState("");
  const [date, setDate] = useState("");
  const needle = search.trim().toLowerCase();
  const visible = items.filter(
    (i) =>
      (!needle ||
        (i.design_id ?? "").toLowerCase().includes(needle) ||
        i.id.toLowerCase().includes(needle) ||
        (i.collection_id ?? "").toLowerCase().includes(needle)) &&
      (!collection || i.collection_id === collection) &&
      (!status || i.status === status) &&
      (!date || (i.started_at ?? "").slice(0, 10) === date),
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3 border border-border bg-card p-4">
        <label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Search
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="run, design or collection…"
            className="mt-1 block border border-border bg-background px-2 py-1 text-foreground outline-none focus:border-primary"
          />
        </label>
        <label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Collection
          <input
            value={collection}
            onChange={(e) => setCollection(e.target.value)}
            placeholder="collection_id"
            className="mt-1 block border border-border bg-background px-2 py-1 text-foreground outline-none focus:border-primary"
          />
        </label>
        <label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Status
          <input
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            placeholder="running|awaiting_approval|failed|complete"
            className="mt-1 block border border-border bg-background px-2 py-1 text-foreground outline-none focus:border-primary"
          />
        </label>
        <label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Date
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="mt-1 block border border-border bg-background px-2 py-1 text-foreground outline-none focus:border-primary"
          />
        </label>
      </div>

      {visible.length === 0 ? (
        <p className="border border-border p-4 font-mono text-xs text-muted-foreground">No runs match.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {visible.map((run) => (
            <li key={run.id} className="border border-border bg-card p-3">
              <Link href={`/runs/${run.id}`} className="font-mono text-sm text-primary">
                {run.design_id ?? run.id}
              </Link>
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                {run.status} · {run.current_node ?? "not started"} · {run.collection_id ?? "no collection"}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
