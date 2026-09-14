"use client";

import Link from "next/link";

import { badgeLabel, type CatalogItem } from "@/lib/catalog";

export function CatalogGrid({ items }: { items: CatalogItem[] }) {
  if (items.length === 0) {
    return (
      <p className="border border-border p-4 font-mono text-xs text-muted-foreground">
        No products in the mirror.
      </p>
    );
  }
  return (
    <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
      {items.map((item) => (
        <li key={item.id} className="border border-border bg-card p-3">
          <Link href={`/catalog/${item.id}`} className="font-mono text-sm text-primary">
            {item.title ?? item.id}
          </Link>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {item.category ?? "uncategorized"} · {item.price !== null ? `$${item.price}` : "no price"} ·{" "}
            {item.status ?? "status unknown"}
            {item.survivor_of ? ` · survivor of ${item.survivor_of}` : ""}
          </p>
          <p
            className={`mt-1 font-mono text-xs ${
              item.invariant.status === "pass" ? "text-primary" : "text-destructive"
            }`}
          >
            {badgeLabel(item)}
          </p>
        </li>
      ))}
    </ul>
  );
}
