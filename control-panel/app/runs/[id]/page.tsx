"use client";

import { use, useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { RunDetailView } from "@/components/runs/run-detail-view";
import { apiFetch } from "@/lib/api";
import { authClient } from "@/lib/auth-client";
import type { RunDetail } from "@/lib/runs";

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: session } = authClient.useSession();
  const role = (session?.user as unknown as { role?: string } | undefined)?.role;
  const canReplay = role === "admin" || role === "operator";

  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [replaying, setReplaying] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setDetail(await apiFetch<RunDetail>(`/api/runs/${id}`));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "load failed");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const onReplay = useCallback(
    async (node: string) => {
      setReplaying(node);
      setError(null);
      try {
        await apiFetch(`/api/runs/${id}/replay`, {
          method: "POST",
          body: JSON.stringify({ node }),
        });
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : "replay failed");
      } finally {
        setReplaying(null);
      }
    },
    [id, load],
  );

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <h1 className="font-sans text-2xl font-semibold">Run {id}</h1>
        {detail ? (
          <RunDetailView
            detail={detail}
            canReplay={canReplay}
            replaying={replaying}
            error={error}
            onReplay={(node) => void onReplay(node)}
          />
        ) : (
          <p className="font-mono text-xs text-muted-foreground">{error ?? "Loading…"}</p>
        )}
      </div>
    </AppShell>
  );
}
