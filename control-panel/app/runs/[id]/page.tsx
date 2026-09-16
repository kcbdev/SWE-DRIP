"use client";

import { use, useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { RunDetailView } from "@/components/runs/run-detail-view";
import { apiFetch } from "@/lib/api";
import { authClient } from "@/lib/auth-client";
import type { LogRow, RunDetail } from "@/lib/runs";
import { subscribeToRunLogs } from "@/lib/sse";

const ACTIVE = new Set(["running", "awaiting_approval"]);

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: session } = authClient.useSession();
  const role = (session?.user as unknown as { role?: string } | undefined)?.role;
  const canReplay = role === "admin" || role === "operator";

  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [logs, setLogs] = useState<LogRow[]>([]);
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

  const loadLogs = useCallback(async () => {
    try {
      const body = await apiFetch<{ items: LogRow[] }>(`/api/runs/${id}/logs?limit=1000`);
      setLogs(body.items);
    } catch {
      // Logs are diagnostic — a failed refresh never hides the run itself.
    }
  }, [id]);

  useEffect(() => {
    void load();
    void loadLogs();
  }, [load, loadLogs]);

  // Live logs while the run is active: SSE when available, polling fallback.
  useEffect(() => {
    if (!detail || !ACTIVE.has(detail.status)) return;
    let timer: ReturnType<typeof setInterval> | undefined;
    const stop = subscribeToRunLogs(
      id,
      (event) =>
        setLogs((prev) =>
          prev.some((r) => r.ts === event.ts && r.node === event.node && r.message === event.message)
            ? prev
            : [...prev, { node: event.node, level: event.level, message: event.message, detail: {}, ts: event.ts }],
        ),
      (streamStatus) => {
        if (streamStatus === "unavailable" && timer === undefined) {
          timer = setInterval(() => void loadLogs(), 5000);
        }
      },
    );
    return () => {
      stop();
      if (timer !== undefined) clearInterval(timer);
    };
  }, [id, detail?.status, loadLogs]);

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
            logs={logs}
            canReplay={canReplay}
            replaying={replaying}
            error={error}
            onReplay={(node) => void onReplay(node)}
            onRefreshLogs={() => {
              void loadLogs();
              void load();
            }}
          />
        ) : (
          <p className="font-mono text-xs text-muted-foreground">{error ?? "Loading…"}</p>
        )}
      </div>
    </AppShell>
  );
}
