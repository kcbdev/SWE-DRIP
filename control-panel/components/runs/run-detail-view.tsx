"use client";

import { useState } from "react";

import {
  nodeSetMismatch,
  prettyState,
  trackerStates,
  type RunDetail,
} from "@/lib/runs";

export interface RunDetailViewProps {
  detail: RunDetail;
  canReplay: boolean;
  replaying: string | null;
  error: string | null;
  onReplay: (node: string) => void;
}

export function RunDetailView({ detail, canReplay, replaying, error, onReplay }: RunDetailViewProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const tracker = trackerStates(detail);
  const mismatch = nodeSetMismatch(detail.nodes);
  const panel = detail.nodes.find((n) => n.node === selected);

  return (
    <div className="flex flex-col gap-4">
      {mismatch.length > 0 ? (
        <p className="border border-destructive p-3 font-mono text-xs text-destructive">
          Node set mismatch vs locked pipeline order: {mismatch.join("; ")}
        </p>
      ) : null}
      {error ? <p className="font-mono text-xs text-destructive">{error}</p> : null}

      <ol className="flex flex-wrap gap-1">
        {tracker.map(({ node, state }) => (
          <li key={node}>
            <button
              type="button"
              onClick={() => {
                setSelected(node);
                setConfirm(null);
              }}
              aria-pressed={selected === node}
              title={`${node}: ${state}`}
              className={`border px-2 py-1 font-mono text-xs ${
                selected === node
                  ? "border-primary text-primary"
                  : state === "complete"
                    ? "border-primary/50 text-foreground"
                    : state === "current"
                      ? "border-primary text-primary"
                      : state === "failed"
                        ? "border-destructive text-destructive"
                        : "border-border text-muted-foreground"
              }`}
            >
              {node} · {state}
            </button>
          </li>
        ))}
      </ol>

      {panel ? (
        <div className="border border-border bg-card p-4">
          <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            {panel.node} {panel.reached ? `· reached${panel.at ? ` · ${panel.at}` : ""}` : "· not reached"}
          </p>
          <pre className="mt-2 overflow-auto font-mono text-xs text-foreground">
            {prettyState(panel.state)}
          </pre>
          {canReplay && panel.reached ? (
            confirm === panel.node ? (
              <span className="mt-3 flex items-center gap-2">
                <span className="font-mono text-xs">Replay from {panel.node}?</span>
                <button
                  type="button"
                  disabled={replaying !== null}
                  onClick={() => {
                    setConfirm(null);
                    onReplay(panel.node);
                  }}
                  className="border border-primary px-3 py-1 font-mono text-xs text-primary disabled:opacity-50"
                >
                  {replaying === panel.node ? "replaying…" : "Confirm replay"}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirm(null)}
                  className="border border-border px-3 py-1 font-mono text-xs"
                >
                  Cancel
                </button>
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setConfirm(panel.node)}
                className="mt-3 border border-border px-3 py-1 font-mono text-xs"
              >
                Replay from here
              </button>
            )
          ) : null}
        </div>
      ) : (
        <p className="font-mono text-xs text-muted-foreground">Select a node to inspect its recorded state.</p>
      )}

      {detail.errors.length > 0 ? (
        <div className="border border-destructive p-3">
          <p className="font-mono text-xs uppercase tracking-widest text-destructive">Run errors</p>
          <ul className="mt-1 font-mono text-xs">
            {detail.errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
