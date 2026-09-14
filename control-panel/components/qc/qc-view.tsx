"use client";

import { useState } from "react";

import {
  agreementLabel,
  barWidth,
  CRITERIA,
  decisionNoteValid,
  swatchStates,
  type Calibration,
  type DesignDetail,
} from "@/lib/designs";

export interface QcViewProps {
  design: DesignDetail;
  calibration: Calibration | null;
  renderSrc: string;
  canDecide: boolean;
  deciding: string | null;
  error: string | null;
  onDecide: (action: "approve" | "reject" | "regenerate", note: string) => void;
}

export function QcView({ design, calibration, renderSrc, canDecide, deciding, error, onDecide }: QcViewProps) {
  const [note, setNote] = useState("");
  const [noteError, setNoteError] = useState<string | null>(null);
  const qc = design.qc;
  const threshold = qc?.pass_threshold ?? 70;

  const decide = (action: "approve" | "reject" | "regenerate") => {
    if (action !== "approve" && !decisionNoteValid(note)) {
      setNoteError(`${action} needs a note (feeds regeneration).`);
      return;
    }
    setNoteError(null);
    onDecide(action, note);
  };

  return (
    <div className="flex flex-col gap-4">
      {error ? <p className="font-mono text-xs text-destructive">{error}</p> : null}
      {noteError ? <p className="font-mono text-xs text-destructive">{noteError}</p> : null}

      <div className="border border-border bg-card p-4">
        {design.render.file_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={renderSrc} alt={`Render for ${design.design_id ?? design.run_id}`} className="max-h-96 border border-border" />
        ) : (
          <p className="font-mono text-xs text-muted-foreground">No render artifact recorded.</p>
        )}
        <p className="mt-2 font-mono text-xs text-muted-foreground">
          {design.context.brief?.subject ?? "untitled"} · run {design.run_id} ·{" "}
          {design.render.model_used ?? "model unknown"}
        </p>
      </div>

      <div className="border border-border p-4">
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Rubric scores (threshold {threshold}, rubric v{qc?.rubric_version ?? "?"})
        </p>
        {qc?.scores ? (
          <ul className="mt-2 flex flex-col gap-2">
            {CRITERIA.map((criterion) => {
              const score = qc.scores?.[criterion] ?? 0;
              return (
                <li key={criterion} className="flex items-center gap-2 font-mono text-xs">
                  <span className="w-32 text-muted-foreground">{criterion}</span>
                  <span className="relative h-3 flex-1 border border-border">
                    <span className="absolute inset-y-0 left-0 bg-primary" style={{ width: `${barWidth(score)}%` }} />
                    <span
                      className="absolute inset-y-0 border-l border-destructive"
                      style={{ left: `${threshold}%` }}
                      title={`threshold ${threshold}`}
                    />
                  </span>
                  <span className="w-16 text-right text-foreground">
                    {score}/100 {score >= threshold ? "pass" : "fail"}
                  </span>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="mt-2 font-mono text-xs text-muted-foreground">No scores recorded yet.</p>
        )}
      </div>

      <div className="border border-border p-4">
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">Colorways</p>
        {design.colorways.length === 0 ? (
          <p className="mt-2 font-mono text-xs text-muted-foreground">no colorways recorded</p>
        ) : (
          <ul className="mt-2 flex flex-wrap gap-2">
            {swatchStates(design.colorways, design.render.colorways_valid).map((swatch) => (
              <li
                key={swatch.label}
                title={swatch.reason ?? "contrast pass"}
                className={`border px-2 py-1 font-mono text-xs ${
                  swatch.valid ? "border-primary text-primary" : "border-destructive text-destructive"
                }`}
              >
                {swatch.label} {swatch.valid ? "✓" : `✗ ${swatch.reason}`}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border border-border p-4">
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">Calibration</p>
        <p className="mt-2 font-mono text-xs text-foreground">{agreementLabel(calibration)}</p>
        {calibration?.note ? (
          <p className="mt-1 font-mono text-xs text-muted-foreground">{calibration.note}</p>
        ) : null}
      </div>

      {canDecide ? (
        <div className="flex flex-wrap items-center gap-2">
          <input
            aria-label="QC decision note"
            placeholder="note (required to reject / regenerate)"
            value={note}
            disabled={deciding !== null}
            onChange={(e) => setNote(e.target.value)}
            className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
          />
          {(["approve", "reject", "regenerate"] as const).map((action) => (
            <button
              key={action}
              type="button"
              disabled={deciding !== null}
              onClick={() => decide(action)}
              className={`border px-3 py-1 font-mono text-xs disabled:opacity-50 ${
                action === "approve" ? "border-primary text-primary" : "border-border"
              }`}
            >
              {deciding === action ? "resuming pipeline…" : action[0].toUpperCase() + action.slice(1)}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
