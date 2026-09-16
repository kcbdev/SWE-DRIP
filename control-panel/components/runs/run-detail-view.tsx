"use client";

import { useState } from "react";

import {
  flowStates,
  formatDuration,
  nodeDurations,
  nodeSetMismatch,
  prettyState,
  type FlowState,
  type LogRow,
  type RunDetail,
} from "@/lib/runs";

export interface RunDetailViewProps {
  detail: RunDetail;
  logs: LogRow[];
  canReplay: boolean;
  replaying: string | null;
  error: string | null;
  onReplay: (node: string) => void;
  onRefreshLogs: () => void;
}

const FLOW_CLASS: Record<FlowState, string> = {
  complete: "border-primary/50 text-foreground",
  current: "border-primary text-primary",
  "awaiting-approval": "border-warning text-warning",
  failed: "border-destructive text-destructive",
  "not-reached": "border-border text-muted-foreground",
};

const LEVEL_CLASS: Record<string, string> = {
  error: "text-destructive",
  warn: "text-warning",
  info: "text-foreground",
  debug: "text-muted-foreground",
};

function formatConfig(node: string, detail: RunDetail): string | null {
  const conf = detail.node_config?.[node];
  if (!conf) return null;
  const parts = [conf.model ?? "deterministic"];
  const params = Object.entries(conf.params ?? {});
  if (params.length > 0) parts.push(params.map(([k, v]) => `${k}=${v}`).join(","));
  if (!conf.enabled) parts.push("disabled");
  return parts.join(" · ");
}

export function RunDetailView({
  detail,
  logs,
  canReplay,
  replaying,
  error,
  onReplay,
  onRefreshLogs,
}: RunDetailViewProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [tab, setTab] = useState<"state" | "logs">("state");
  const flow = flowStates(detail);
  const mismatch = nodeSetMismatch(detail.nodes);
  const durations = nodeDurations(logs);
  const panel = detail.nodes.find((n) => n.node === selected);
  const panelLogs = panel ? logs.filter((l) => l.node === panel.node) : [];
  const panelConfig = panel ? formatConfig(panel.node, detail) : null;

  return (
    <div className="flex flex-col gap-4">
      {mismatch.length > 0 ? (
        <p className="border border-destructive p-3 font-mono text-xs text-destructive">
          Node set mismatch vs locked pipeline order: {mismatch.join("; ")}
        </p>
      ) : null}
      {error ? <p className="font-mono text-xs text-destructive">{error}</p> : null}

      <ol className="flex flex-wrap gap-1">
        {flow.map(({ node, state }) => (
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
                selected === node ? "border-primary text-primary" : FLOW_CLASS[state]
              }`}
            >
              {node} · {state}
              {durations[node] ? ` · ${formatDuration(durations[node])}` : null}
            </button>
          </li>
        ))}
      </ol>

      {panel ? (
        <div className="border border-border bg-card p-4">
          <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            {panel.node} {panel.reached ? `· reached${panel.at ? ` · ${panel.at}` : ""}` : "· not reached"}
            {durations[panel.node] ? ` · ${formatDuration(durations[panel.node])}` : null}
          </p>
          {panelConfig ? (
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              run config: {panelConfig}
            </p>
          ) : null}

          <div className="mt-3 flex gap-1" role="tablist" aria-label={`${panel.node} inspector`}>
            {(["state", "logs"] as const).map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
                className={`border px-2 py-0.5 font-mono text-xs ${
                  tab === t ? "border-primary text-primary" : "border-border text-muted-foreground"
                }`}
              >
                {t === "logs" ? `logs (${panelLogs.length})` : "state"}
              </button>
            ))}
            <button
              type="button"
              onClick={onRefreshLogs}
              className="border border-border px-2 py-0.5 font-mono text-xs text-muted-foreground hover:text-foreground"
            >
              Refresh logs
            </button>
          </div>

          {tab === "state" ? (
            <pre className="mt-2 overflow-auto font-mono text-xs text-foreground">
              {prettyState(panel.state)}
            </pre>
          ) : panelLogs.length === 0 ? (
            <p className="mt-2 font-mono text-xs text-muted-foreground">
              No log rows for {panel.node} yet — offline runs keep logs in memory only.
            </p>
          ) : (
            <ul className="mt-2 flex flex-col gap-1">
              {panelLogs.map((row, i) => (
                <li key={i} className="border border-border px-2 py-1 font-mono text-xs">
                  <span className={LEVEL_CLASS[row.level] ?? "text-foreground"}>[{row.level}]</span>{" "}
                  <span className="text-muted-foreground">{row.ts}</span>{" "}
                  <span className="text-foreground">{row.message}</span>
                </li>
              ))}
            </ul>
          )}

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
