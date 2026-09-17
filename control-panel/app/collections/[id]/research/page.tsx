"use client";

import { use, useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ResearchView } from "@/components/collections/research-view";
import { StylesManager } from "@/components/collections/styles-manager";
import { apiFetch } from "@/lib/api";
import { authClient } from "@/lib/auth-client";
import type { CollectionRecord } from "@/lib/collections";
import {
  addInspirationLink,
  decideResearchApproval,
  deleteInspirationAsset,
  getInspiration,
  getResearchLogs,
  getResearchRun,
  getRotation,
  getStyles,
  listResearchApprovals,
  listResearchRuns,
  createStyle,
  startResearchRun,
  updateStyle,
  uploadInspirationAsset,
  type InspirationListing,
  type ResearchDetail,
  type ResearchGateItem,
  type ResearchLogRow,
  type ResearchRunRow,
  type RotationQueue,
  type StylesRepo,
} from "@/lib/research";

const TERMINAL = new Set(["complete", "failed"]);

export default function CollectionResearchPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
  const { data: session } = authClient.useSession();
  const role = (session?.user as unknown as { role?: string } | undefined)?.role;

  const [record, setRecord] = useState<CollectionRecord | null>(null);
  const [inspiration, setInspiration] = useState<InspirationListing>({ assets: [], refs: [] });
  const [rotation, setRotation] = useState<RotationQueue | null>(null);
  const [runs, setRuns] = useState<ResearchRunRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<ResearchDetail | null>(null);
  const [logs, setLogs] = useState<ResearchLogRow[]>([]);
  const [logTab, setLogTab] = useState<"state" | "logs">("state");
  const [gate, setGate] = useState<ResearchGateItem | null>(null);
  const [repo, setRepo] = useState<StylesRepo | null>(null);
  const [lastAffected, setLastAffected] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [rec, insp, rot, runList, approvals, styles] = await Promise.all([
        apiFetch<CollectionRecord>(`/api/collections/${id}`),
        getInspiration(id),
        getRotation(),
        listResearchRuns(),
        listResearchApprovals(),
        getStyles(),
      ]);
      setRecord(rec);
      setInspiration(insp);
      setRotation(rot);
      const mine = runList.items.filter((r) => r.collection_slug === id);
      setRuns(mine);
      setSelectedId((prev) => prev ?? (mine[0]?.id ?? null));
      const open = approvals.items.find(
        (g) => g.entity_ref?.id === id && g.status === "pending",
      ) ?? null;
      setGate(open);
      setRepo(styles);
    } catch (err) {
      setError(err instanceof Error ? err.message : "load failed");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const loadRun = useCallback(
    async (runId: string) => {
      try {
        const [detail, logRows] = await Promise.all([getResearchRun(runId), getResearchLogs(runId)]);
        setSelectedRun(detail);
        setLogs(logRows.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : "run load failed");
      }
    },
    [],
  );

  useEffect(() => {
    if (selectedId) void loadRun(selectedId);
    else {
      setSelectedRun(null);
      setLogs([]);
    }
  }, [selectedId, loadRun]);

  // Poll while the selected run is non-terminal (quiet otherwise).
  useEffect(() => {
    if (!selectedRun || TERMINAL.has(selectedRun.status)) return;
    const timer = setInterval(() => {
      void loadRun(selectedRun.id);
      void load();
    }, 5000);
    return () => clearInterval(timer);
  }, [selectedRun, loadRun, load]);

  const act = async (fn: () => Promise<unknown>) => {
    setActing(true);
    setError(null);
    try {
      await fn();
      await load();
      if (selectedId) await loadRun(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "action failed");
    } finally {
      setActing(false);
    }
  };

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <h1 className="font-sans text-2xl font-semibold">Collection research</h1>
        {!record ? (
          <p className="font-mono text-xs text-muted-foreground">{error ?? "Loading…"}</p>
        ) : (
          <>
            <ResearchView
              slug={id}
              role={role}
              apiBase={apiBase}
              contract={record.contract}
              inspiration={inspiration}
              rotation={rotation}
              runs={runs}
              selectedRun={selectedRun}
              logs={logs}
              logTab={logTab}
              onLogTab={setLogTab}
              gate={gate}
              error={error}
              acting={acting}
              onStartRun={() => void act(() => startResearchRun(id))}
              onSelectRun={(runId) => setSelectedId(runId)}
              onDecideGate={(action, note, contract) =>
                void act(async () => {
                  if (!gate) throw new Error("no open gate for this collection");
                  await decideResearchApproval(gate.id, action, note, contract);
                })
              }
              onUpload={(file, note, sourceUrl) =>
                void act(() => uploadInspirationAsset(apiBase, id, file, note, sourceUrl))
              }
              onAddLink={(url, note) => void act(() => addInspirationLink(id, url, note))}
              onDeleteAsset={(assetId) => void act(() => deleteInspirationAsset(id, assetId))}
              onApproveDraft={() =>
                void act(() => apiFetch(`/api/collections/${id}/approve`, { method: "POST" }))
              }
            />
            <StylesManager
              repo={repo}
              role={role}
              error={null}
              acting={acting}
              lastAffected={lastAffected}
              onCreate={(name, definition) =>
                void act(async () => {
                  if (!repo) throw new Error("style repository unavailable");
                  const result = await createStyle(name, definition, repo.version);
                  setRepo({ version: result.version, styles: result.styles });
                  setLastAffected(result.affected_contracts);
                })
              }
              onUpdate={(oldName, patch) =>
                void act(async () => {
                  if (!repo) throw new Error("style repository unavailable");
                  const result = await updateStyle(oldName, repo.version, patch);
                  setRepo({ version: result.version, styles: result.styles });
                  setLastAffected(result.affected_contracts);
                })
              }
            />
          </>
        )}
      </div>
    </AppShell>
  );
}
