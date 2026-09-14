"use client";

import { use, useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { QcView } from "@/components/qc/qc-view";
import { apiFetch } from "@/lib/api";
import { authClient } from "@/lib/auth-client";
import type { Calibration, DesignDetail } from "@/lib/designs";

interface QueueItem {
  id: number;
  run_id: string;
  node: string;
}

export default function DesignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: session } = authClient.useSession();
  const role = (session?.user as unknown as { role?: string } | undefined)?.role;
  const canDecide = role === "admin" || role === "operator";

  const [design, setDesign] = useState<DesignDetail | null>(null);
  const [calibration, setCalibration] = useState<Calibration | null>(null);
  const [gateId, setGateId] = useState<number | null>(null);
  const [deciding, setDeciding] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setDesign(await apiFetch<DesignDetail>(`/api/designs/${id}`));
      setCalibration(await apiFetch<Calibration>(`/api/designs/${id}/calibration`));
      const queue = await apiFetch<{ items: QueueItem[] }>("/api/approvals");
      const gate = queue.items.find((row) => row.run_id === id && row.node === "aesthetic_qc");
      setGateId(gate?.id ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "load failed");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const onDecide = useCallback(
    async (action: "approve" | "reject" | "regenerate", note: string) => {
      if (gateId === null) {
        setError("No open QC gate for this design (already decided?).");
        return;
      }
      setDeciding(action);
      setError(null);
      try {
        await apiFetch(`/api/approvals/${gateId}/decision`, {
          method: "POST",
          body: JSON.stringify({ action, note: note || undefined }),
        });
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : "decision failed");
      } finally {
        setDeciding(null);
      }
    },
    [gateId, load],
  );

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <h1 className="font-sans text-2xl font-semibold">Design QC</h1>
        {design ? (
          <QcView
            design={design}
            calibration={calibration}
            renderSrc={`/api/designs/${id}/render`}
            canDecide={canDecide && gateId !== null}
            deciding={deciding}
            error={error}
            onDecide={(action, note) => void onDecide(action, note)}
          />
        ) : (
          <p className="font-mono text-xs text-muted-foreground">{error ?? "Loading…"}</p>
        )}
      </div>
    </AppShell>
  );
}
