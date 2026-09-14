"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import { authClient } from "@/lib/auth-client";
import type { CollectionRecord } from "@/lib/collections";
import { CollectionsList } from "@/components/collections/collections-list";

export default function CollectionsPage() {
  const { data: session } = authClient.useSession();
  const role = (session?.user as unknown as { role?: string } | undefined)?.role;
  const [items, setItems] = useState<CollectionRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ items: CollectionRecord[] }>("/api/collections")
      .then((body) => setItems(body.items))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "load failed"));
  }, []);

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <h1 className="font-sans text-2xl font-semibold">Collections</h1>
        {error ? <p className="font-mono text-xs text-destructive">{error}</p> : null}
        <CollectionsList items={items} canCreate={role === "admin"} />
      </div>
    </AppShell>
  );
}
