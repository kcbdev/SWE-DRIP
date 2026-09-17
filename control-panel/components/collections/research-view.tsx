"use client";

import { useState } from "react";

import type { CollectionContract } from "@/lib/collections";
import {
  boardDisplayRef,
  boardImageUrl,
  canCurate,
  canDecideResearch,
  inspirationFileUrl,
  parseLines,
  stageLabel,
  type InspirationListing,
  type ResearchDetail,
  type ResearchGateItem,
  type ResearchLogRow,
  type ResearchRunRow,
  type RotationQueue,
} from "@/lib/research";

export interface ResearchViewProps {
  slug: string;
  role: string | undefined;
  contract: CollectionContract;
  inspiration: InspirationListing;
  rotation: RotationQueue | null;
  runs: ResearchRunRow[];
  selectedRun: ResearchDetail | null;
  logs: ResearchLogRow[];
  logTab: "state" | "logs";
  onLogTab: (tab: "state" | "logs") => void;
  gate: ResearchGateItem | null;
  error: string | null;
  acting: boolean;
  onStartRun: () => void;
  onSelectRun: (runId: string) => void;
  onDecideGate: (action: "approve" | "reject" | "regenerate", note: string, contract?: Record<string, unknown>) => void;
  onUpload: (file: File, note: string, sourceUrl: string) => void;
  onAddLink: (url: string, note: string) => void;
  onDeleteAsset: (assetId: string) => void;
  onApproveDraft: () => void;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-border p-4">
      <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">{title}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export function ResearchView(props: ResearchViewProps) {
  const { slug, role, contract } = props;
  const curate = canCurate(role);
  const decide = canDecideResearch(role);

  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [linkNote, setLinkNote] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [gateAction, setGateAction] = useState<"approve" | "reject" | "regenerate" | null>(null);
  const [gateNote, setGateNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [editTheme, setEditTheme] = useState("");
  const [editDescriptors, setEditDescriptors] = useState("");
  const [editAvoid, setEditAvoid] = useState("");
  const [startConfirm, setStartConfirm] = useState(false);
  const [activateConfirm, setActivateConfirm] = useState(false);

  const boardRefs = contract.mood_board ?? [];
  const descriptors = contract.style_descriptors ?? [];
  const avoid = contract.avoid ?? [];
  const flags = props.selectedRun?.diversity_flags ?? props.gate?.payload.diversity_flags ?? [];
  // In-flight board: the selected run rendered a sheet the contract does not
  // name yet (pre-approval). Shown distinctly until the handoff lands it.
  const runBoardRef = boardDisplayRef(props.selectedRun?.board?.file_ref);
  const showRunBoard = runBoardRef !== null && !boardRefs.includes(runBoardRef);

  const editEmpty =
    !editTheme.trim() && parseLines(editDescriptors).length === 0 && parseLines(editAvoid).length === 0;

  const submitEditApprove = () => {
    const contract: Record<string, unknown> = {};
    if (editTheme.trim()) contract.theme = editTheme.trim();
    const parsedDescriptors = parseLines(editDescriptors);
    if (parsedDescriptors.length > 0) contract.style_descriptors = parsedDescriptors;
    const parsedAvoid = parseLines(editAvoid);
    if (parsedAvoid.length > 0) contract.avoid = parsedAvoid;
    props.onDecideGate("approve", gateNote, contract);
    setEditing(false);
    setGateAction(null);
  };

  return (
    <div className="flex flex-col gap-4">
      <h2 className="font-sans text-xl font-semibold">
        Research <span className="font-mono text-xs text-muted-foreground">{slug}</span>
      </h2>
      {props.error ? <p className="font-mono text-xs text-destructive">{props.error}</p> : null}

      {props.rotation ? (
        <p className="font-mono text-xs text-muted-foreground">
          Rotation: next candidate {props.rotation.next_candidate ?? "—"} · {props.rotation.drafts}{" "}
          drafts · {props.rotation.actives} active
        </p>
      ) : null}

      <Section title="Mood board">
        {boardRefs.length === 0 && !showRunBoard ? (
          <p className="font-mono text-xs text-muted-foreground">
            No board yet — curate inspiration below, then start a research run.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {boardRefs.map((ref) => (
              <li key={ref}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={boardImageUrl(slug, ref)}
                  alt={`Mood board ${ref}`}
                  className="max-h-96 border border-border"
                />
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  {ref} · board v{contract.board_version ?? 1}
                </p>
              </li>
            ))}
            {showRunBoard && runBoardRef ? (
              <li key={`run-${runBoardRef}`}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={boardImageUrl(slug, runBoardRef)}
                  alt={`In-flight board ${runBoardRef}`}
                  className="max-h-96 border border-border"
                />
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  {runBoardRef} · in-flight (run {props.selectedRun?.id.slice(0, 12)}…) — lands
                  on gate approval
                </p>
              </li>
            ) : null}
          </ul>
        )}
      </Section>

      <Section title="Locked directives">
        <dl className="grid grid-cols-2 gap-2 font-mono text-xs">
          <dt className="text-muted-foreground">style_archetype</dt>
          <dd>{contract.style_archetype}</dd>
          <dt className="text-muted-foreground">style_descriptors</dt>
          <dd>{descriptors.length > 0 ? descriptors.join(" · ") : "—"}</dd>
          <dt className="text-muted-foreground">palette</dt>
          <dd>{contract.illustration_rules.palette.join(" · ") || "—"}</dd>
          <dt className="text-muted-foreground">avoid</dt>
          <dd>{avoid.length > 0 ? avoid.join(" · ") : "—"}</dd>
          <dt className="text-muted-foreground">board_version</dt>
          <dd>{contract.board_version ?? 1}</dd>
        </dl>
      </Section>

      <Section title="Lineage / diversity flags">
        {flags.length === 0 ? (
          <p className="font-mono text-xs text-muted-foreground">No flags — distinct from lineage.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {flags.map((flag, i) => (
              <li key={i} className="font-mono text-xs text-primary">
                {flag}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={`Inspiration (${props.inspiration.assets.length} assets · ${props.inspiration.refs.length} links)`}>
        {props.inspiration.assets.length === 0 && props.inspiration.refs.length === 0 ? (
          <p className="font-mono text-xs text-muted-foreground">Nothing curated yet.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {props.inspiration.assets.length > 0 ? (
              <ul className="grid grid-cols-2 gap-2">
                {props.inspiration.assets.map((asset) => (
                  <li key={asset.id} className="border border-border p-2">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={inspirationFileUrl(slug, asset.id)}
                      alt={asset.note || asset.filename}
                      className="max-h-48 border border-border"
                    />
                    <p className="mt-1 font-mono text-xs text-muted-foreground">
                      {asset.note || asset.filename}
                      {asset.source_url ? ` · ${asset.source_url}` : ""}
                    </p>
                    {curate ? (
                      deleteId === asset.id ? (
                        <span className="mt-1 flex items-center gap-2">
                          <span className="font-mono text-xs">Delete this asset?</span>
                          <button
                            type="button"
                            disabled={props.acting}
                            onClick={() => {
                              setDeleteId(null);
                              props.onDeleteAsset(asset.id);
                            }}
                            className="border border-destructive px-2 py-0.5 font-mono text-xs text-destructive"
                          >
                            Confirm delete
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteId(null)}
                            className="border border-border px-2 py-0.5 font-mono text-xs"
                          >
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setDeleteId(asset.id)}
                          className="mt-1 border border-border px-2 py-0.5 font-mono text-xs"
                        >
                          Delete…
                        </button>
                      )
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
            {props.inspiration.refs.length > 0 ? (
              <ul className="flex flex-col gap-1">
                {props.inspiration.refs.map((ref, i) => (
                  <li key={i} className="font-mono text-xs">
                    <span className="text-primary">{ref.url}</span>
                    {ref.note ? <span className="text-muted-foreground"> — {ref.note}</span> : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        )}
        {curate ? (
          <div className="mt-3 flex flex-col gap-3 border-t border-border pt-3">
            <div className="flex flex-wrap items-center gap-2">
              <input
                aria-label="Inspiration image file"
                type="file"
                accept="image/png,image/jpeg"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="font-mono text-xs"
              />
              <input
                aria-label="Asset note"
                placeholder="note (optional)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
              />
              <input
                aria-label="Asset source URL"
                placeholder="source URL (optional)"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
              />
              <button
                type="button"
                disabled={props.acting || !file}
                title={file ? "Upload asset" : "Choose a file first"}
                onClick={() => {
                  if (!file) return;
                  props.onUpload(file, note, sourceUrl);
                  setFile(null);
                  setNote("");
                  setSourceUrl("");
                }}
                className="border border-primary px-3 py-1 font-mono text-xs text-primary disabled:opacity-40"
              >
                Upload
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                aria-label="Link URL"
                placeholder="https://…"
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
              />
              <input
                aria-label="Link note"
                placeholder="note (optional)"
                value={linkNote}
                onChange={(e) => setLinkNote(e.target.value)}
                className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
              />
              <button
                type="button"
                disabled={props.acting || !linkUrl.trim()}
                onClick={() => {
                  props.onAddLink(linkUrl.trim(), linkNote);
                  setLinkUrl("");
                  setLinkNote("");
                }}
                className="border border-primary px-3 py-1 font-mono text-xs text-primary disabled:opacity-40"
              >
                Add link
              </button>
            </div>
          </div>
        ) : null}
      </Section>

      <Section title="Research runs">
        {curate ? (
          startConfirm ? (
            <span className="flex items-center gap-2">
              <span className="font-mono text-xs">Start a research run? It spends budget.</span>
              <button
                type="button"
                disabled={props.acting}
                onClick={() => {
                  setStartConfirm(false);
                  props.onStartRun();
                }}
                className="border border-primary px-3 py-1 font-mono text-xs text-primary"
              >
                Confirm start
              </button>
              <button
                type="button"
                onClick={() => setStartConfirm(false)}
                className="border border-border px-3 py-1 font-mono text-xs"
              >
                Cancel
              </button>
            </span>
          ) : (
            <button
              type="button"
              onClick={() => setStartConfirm(true)}
              className="border border-primary px-3 py-1 font-mono text-xs text-primary"
            >
              Start research run
            </button>
          )
        ) : null}
        {props.runs.length === 0 ? (
          <p className="mt-2 font-mono text-xs text-muted-foreground">No research runs yet.</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1">
            {props.runs.map((run) => (
              <li key={run.id}>
                <button
                  type="button"
                  onClick={() => props.onSelectRun(run.id)}
                  className="font-mono text-xs text-primary"
                >
                  {run.id.slice(0, 12)}… · {stageLabel(run.current_stage)} ·{" "}
                  {run.board_version ? `board v${run.board_version}` : "no board"}
                  {run.diversity_flags.length > 0 ? ` · ${run.diversity_flags.length} flags` : ""}
                </button>
              </li>
            ))}
          </ul>
        )}
        {props.selectedRun ? (
          <div className="mt-3 border-t border-border pt-3">
            <div className="flex gap-2">
              {(["state", "logs"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => props.onLogTab(tab)}
                  className={`border px-3 py-1 font-mono text-xs ${
                    props.logTab === tab ? "border-primary text-primary" : "border-border"
                  }`}
                >
                  {tab === "state" ? "State" : "Logs"}
                </button>
              ))}
            </div>
            {props.logTab === "state" ? (
              <ul className="mt-2 flex flex-col gap-1">
                {props.selectedRun.nodes.map((node) => (
                  <li key={node.node} className="font-mono text-xs">
                    <span className={node.reached ? "text-primary" : "text-muted-foreground"}>
                      {node.reached ? "●" : "○"} {node.node}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <ul className="mt-2 flex max-h-64 flex-col gap-1 overflow-auto">
                {props.logs.length === 0 ? (
                  <li className="font-mono text-xs text-muted-foreground">No log rows yet.</li>
                ) : (
                  props.logs.map((row, i) => (
                    <li key={i} className="font-mono text-xs">
                      <span className="text-muted-foreground">
                        [{row.node}]{" "}
                      </span>
                      {row.message}
                    </li>
                  ))
                )}
              </ul>
            )}
            {props.selectedRun.errors.length > 0 ? (
              <ul className="mt-2 flex flex-col gap-1">
                {props.selectedRun.errors.map((err, i) => (
                  <li key={i} className="font-mono text-xs text-destructive">
                    {err}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </Section>

      {props.gate ? (
        <Section title={`CEO gate — ${props.gate.run_id.slice(0, 12)}…`}>
          <p className="font-mono text-xs text-muted-foreground">
            Draft {(props.gate.payload.draft.collection_id as string) ?? slug} · board v
            {props.gate.payload.board.board_version ?? "?"} ·{" "}
            {props.gate.payload.diversity_flags.length} flags
          </p>
          {decide ? (
            <div className="mt-2 flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <input
                  aria-label="Gate decision note"
                  placeholder="note (optional)"
                  value={gateNote}
                  onChange={(e) => setGateNote(e.target.value)}
                  className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
                />
                {gateAction ? (
                  <span className="flex items-center gap-2">
                    <span className="font-mono text-xs">Confirm {gateAction}?</span>
                    <button
                      type="button"
                      disabled={props.acting}
                      onClick={() => {
                        const action = gateAction;
                        setGateAction(null);
                        props.onDecideGate(action, gateNote);
                      }}
                      className="border border-primary px-3 py-1 font-mono text-xs text-primary"
                    >
                      Confirm {gateAction}
                    </button>
                    <button
                      type="button"
                      onClick={() => setGateAction(null)}
                      className="border border-border px-3 py-1 font-mono text-xs"
                    >
                      Cancel
                    </button>
                  </span>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => setGateAction("approve")}
                      className="border border-primary px-3 py-1 font-mono text-xs text-primary"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditing(true)}
                      className="border border-border px-3 py-1 font-mono text-xs"
                    >
                      Edit and approve…
                    </button>
                    <button
                      type="button"
                      onClick={() => setGateAction("reject")}
                      className="border border-destructive px-3 py-1 font-mono text-xs text-destructive"
                    >
                      Reject
                    </button>
                  </>
                )}
              </div>
              {editing ? (
                <div className="flex flex-col gap-2 border border-border p-2">
                  <input
                    aria-label="Edited theme"
                    placeholder="theme override (optional)"
                    value={editTheme}
                    onChange={(e) => setEditTheme(e.target.value)}
                    className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
                  />
                  <textarea
                    aria-label="Edited style descriptors"
                    placeholder="style descriptors, one per line (optional)"
                    value={editDescriptors}
                    onChange={(e) => setEditDescriptors(e.target.value)}
                    rows={3}
                    className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
                  />
                  <textarea
                    aria-label="Edited avoid list"
                    placeholder="avoid, one per line (optional)"
                    value={editAvoid}
                    onChange={(e) => setEditAvoid(e.target.value)}
                    rows={2}
                    className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={props.acting || editEmpty}
                      title={editEmpty ? "Change something first" : "Submit CEO edits"}
                      onClick={submitEditApprove}
                      className="border border-primary px-3 py-1 font-mono text-xs text-primary disabled:opacity-40"
                    >
                      Confirm edit and approve
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditing(false)}
                      className="border border-border px-3 py-1 font-mono text-xs"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </Section>
      ) : null}

      {props.selectedRun?.status === "complete" && contract.status === "draft" && decide ? (
        <Section title="Activate">
          {activateConfirm ? (
            <span className="flex items-center gap-2">
              <span className="font-mono text-xs">Approve this draft to active?</span>
              <button
                type="button"
                disabled={props.acting}
                onClick={() => {
                  setActivateConfirm(false);
                  props.onApproveDraft();
                }}
                className="border border-primary px-3 py-1 font-mono text-xs text-primary"
              >
                Confirm activate
              </button>
              <button
                type="button"
                onClick={() => setActivateConfirm(false)}
                className="border border-border px-3 py-1 font-mono text-xs"
              >
                Cancel
              </button>
            </span>
          ) : (
            <button
              type="button"
              onClick={() => setActivateConfirm(true)}
              className="border border-primary px-3 py-1 font-mono text-xs text-primary"
            >
              Approve to active
            </button>
          )}
        </Section>
      ) : null}
    </div>
  );
}
