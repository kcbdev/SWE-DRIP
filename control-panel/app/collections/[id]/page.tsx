"use client";

import { use, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { CollectionDetail } from "@/components/collections/collection-detail";
import { apiFetch } from "@/lib/api";
import { authClient } from "@/lib/auth-client";
import type { CollectionRecord } from "@/lib/collections";

export default function CollectionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: session } = authClient.useSession();
  const role = (session?.user as unknown as { role?: string } | undefined)?.role;
  const [record, setRecord] = useState<CollectionRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const load = async () => {
    try {
      setRecord(await apiFetch<CollectionRecord>(`/api/collections/${id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "load failed");
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const act = async (path: string, body?: unknown) => {
    setActing(true);
    setError(null);
    try {
      await apiFetch(path, { method: "POST", body: JSON.stringify(body ?? {}) });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "action failed");
    } finally {
      setActing(false);
    }
  };

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <h1 className="font-sans text-2xl font-semibold">Collection</h1>
        {record ? (
          <CollectionDetail
            record={record}
            role={role}
            error={error}
            acting={acting}
            onApprove={() => void act(`/api/collections/${id}/approve`)}
            onRetire={(survivors) =>
              void act(`/api/collections/${id}/retire`, {
                survivor_product_ids: survivors,
              })
            }
          />
        ) : (
          <p className="font-mono text-xs text-muted-foreground">
            {error ?? "Loading…"}
          </p>
        )}
      </div>
    </AppShell>
  );
}
