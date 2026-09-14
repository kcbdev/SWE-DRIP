"use client";

import { useState } from "react";

import { lifecycleDaysLeft, parseSurvivors, type CollectionRecord } from "@/lib/collections";

export interface CollectionDetailProps {
  record: CollectionRecord;
  role: string | undefined;
  error: string | null;
  acting: boolean;
  onApprove: () => void;
  onRetire: (survivors: string[]) => void;
}

export function CollectionDetail({ record, role, error, acting, onApprove, onRetire }: CollectionDetailProps) {
  const { contract } = record;
  const [confirm, setConfirm] = useState<"approve" | "retire" | null>(null);
  const [survivors, setSurvivors] = useState("");
  const daysLeft = lifecycleDaysLeft(contract);
  const canApprove = role === "admin" || role === "operator";
  const canRetire = role === "admin";

  return (
    <div className="flex flex-col gap-4">
      <h2 className="font-sans text-xl font-semibold">
        {contract.theme} <span className="font-mono text-xs text-muted-foreground">{contract.status}</span>
      </h2>
      {error ? <p className="font-mono text-xs text-destructive">{error}</p> : null}

      <dl className="grid grid-cols-2 gap-2 border border-border bg-card p-4 font-mono text-xs">
        <dt className="text-muted-foreground">collection_id</dt>
        <dd>{contract.collection_id}</dd>
        <dt className="text-muted-foreground">style_archetype</dt>
        <dd>{contract.style_archetype}</dd>
        <dt className="text-muted-foreground">line_weight</dt>
        <dd>{contract.illustration_rules.line_weight ?? "—"}</dd>
        <dt className="text-muted-foreground">targets</dt>
        <dd>
          {contract.product_count_target ?? "—"} products · {contract.lifecycle_days ?? "—"} days
          {daysLeft !== null ? ` · ${daysLeft}d left` : ""}
        </dd>
        <dt className="text-muted-foreground">kpi_thresholds</dt>
        <dd>
          ≥{contract.kpi_thresholds.min_units ?? "?"} units · ≥
          {contract.kpi_thresholds.min_conversion ?? "?"} conv ·{" "}
          {contract.kpi_thresholds.eval_window_days ?? "?"}d window
        </dd>
        <dt className="text-muted-foreground">created</dt>
        <dd>
          {contract.created_by} · {contract.created_at}
        </dd>
        <dt className="text-muted-foreground">approved / retired</dt>
        <dd>
          {contract.approved_at ?? "—"} / {contract.retired_at ?? "—"}
        </dd>
        {contract.survivor_products?.length ? (
          <>
            <dt className="text-muted-foreground">survivors (live)</dt>
            <dd className="text-primary">{contract.survivor_products.join(", ")}</dd>
          </>
        ) : null}
      </dl>

      <div className="border border-border p-4">
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">Palette</p>
        <div className="mt-2 flex gap-2">
          {contract.illustration_rules.palette.length === 0 ? (
            <span className="font-mono text-xs text-muted-foreground">no colors set</span>
          ) : (
            contract.illustration_rules.palette.map((color) => (
              <span key={color} className="flex items-center gap-1 font-mono text-xs">
                <span
                  aria-hidden
                  className="inline-block h-4 w-4 border border-border"
                  style={{ backgroundColor: color }}
                />
                {color}
              </span>
            ))
          )}
        </div>
      </div>

      <div className="border border-border p-4">
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Placement templates
        </p>
        {contract.placement_templates.length === 0 ? (
          <p className="mt-2 font-mono text-xs text-muted-foreground">no templates set</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {contract.placement_templates.map((t, i) => (
              <li key={i} className="font-mono text-xs">
                <span className="text-primary">{t.design_type}</span>
                <span className="text-muted-foreground">
                  {"  "}front:{t.front} back:{t.back} sleeve:{t.sleeve}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border border-border p-4">
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">Colorways</p>
        <p className="mt-2 font-mono text-xs">
          {contract.garment_colorways.length === 0
            ? "none set"
            : contract.garment_colorways.map((c) => `${c.base}${c.contrast_pass ? " ✓" : ""}`).join(" · ")}
        </p>
      </div>

      <div className="border border-border p-4">
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">KPI history</p>
        <p className="mt-2 font-mono text-xs text-muted-foreground">
          No analytics yet — chart lands with catalog-analytics (PBI-031).
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {contract.status === "draft" && canApprove ? (
          confirm === "approve" ? (
            <span className="flex items-center gap-2">
              <span className="font-mono text-xs">Approve this candidate?</span>
              <button
                type="button"
                disabled={acting}
                onClick={() => {
                  setConfirm(null);
                  onApprove();
                }}
                className="border border-primary px-3 py-1 font-mono text-xs text-primary"
              >
                Confirm approve
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
              onClick={() => setConfirm("approve")}
              className="border border-primary px-3 py-1 font-mono text-xs text-primary"
            >
              Approve
            </button>
          )
        ) : null}
        {contract.status === "active" && canRetire ? (
          confirm === "retire" ? (
            <span className="flex flex-wrap items-center gap-2">
              <input
                aria-label="Survivor product ids"
                placeholder="survivor product ids, comma-separated"
                value={survivors}
                onChange={(e) => setSurvivors(e.target.value)}
                className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
              />
              <button
                type="button"
                disabled={acting}
                onClick={() => {
                  setConfirm(null);
                  onRetire(parseSurvivors(survivors));
                }}
                className="border border-destructive px-3 py-1 font-mono text-xs text-destructive"
              >
                Confirm retire
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
              onClick={() => setConfirm("retire")}
              className="border border-destructive px-3 py-1 font-mono text-xs text-destructive"
            >
              Retire…
            </button>
          )
        ) : null}
      </div>
    </div>
  );
}
