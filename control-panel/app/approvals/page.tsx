"use client";

import { useCallback, useEffect, useState } from "react";

import { ApprovalsView } from "@/components/approvals/approvals-view";
import { AppShell } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import type { ApprovalItem, DecisionAction, DecisionResult } from "@/lib/approvals";
import { authClient } from "@/lib/auth-client";
import { subscribeToRuns } from "@/lib/sse";

export default function ApprovalsPage() {
  const { data: session } = authClient.useSession();
  const role = (session?.user as unknown as { role?: string } | undefined)?.role;
  const canDecide = role === "admin" || role === "operator";

  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [deciding, setDeciding] = useState<Record<number, DecisionAction>>({});
  const [error, setError] = useState<string | null>(null);
  const [streamLive, setStreamLive] = useState(false);

  const load = useCallback(async () => {
    try {
      const body = await apiFetch<{ items: ApprovalItem[] }>("/api/approvals");
      setItems(body.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load approvals");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Live updates: any push refetches the queue (reconciles + inserts).
  useEffect(
    () =>
      subscribeToRuns(
        () => void load(),
        (status) => setStreamLive(status === "live"),
      ),
    [load],
  );

  const onDecide = useCallback(
    async (item: ApprovalItem, action: DecisionAction, note: string) => {
      setDeciding((current) => ({ ...current, [item.id]: action }));
      setError(null);
      try {
        const result = await apiFetch<DecisionResult>(`/api/approvals/${item.id}/decision`, {
          method: "POST",
          body: JSON.stringify({ action, note: note || undefined }),
        });
        // Backend-confirmed: drop the decided row (a later push refetch
        // reconciles anything we missed). No optimistic data is kept.
        if (result.status !== "pending") {
          setItems((current) => current.filter((row) => row.id !== item.id));
        }
      } catch (err) {
        // Failed decisions surface and restore prior state (row stays).
        setError(
          `Decision on #${item.id} failed: ${err instanceof Error ? err.message : "unknown error"}`,
        );
      } finally {
        setDeciding((current) => {
          const next = { ...current };
          delete next[item.id];
          return next;
        });
      }
    },
    [],
  );

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <h1 className="font-sans text-2xl font-semibold">Approvals</h1>
        <ApprovalsView
          items={items}
          canDecide={canDecide}
          deciding={deciding}
          error={error}
          streamLive={streamLive}
          onDecide={(item, action, note) => void onDecide(item, action, note)}
          onRefresh={() => void load()}
        />
      </div>
    </AppShell>
  );
}
