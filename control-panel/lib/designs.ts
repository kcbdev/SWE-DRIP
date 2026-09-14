/** Design QC UI types + pure helpers (PBI-024; data via PBI-016/023 APIs). */

export interface QcScores {
  style_cohesion: number;
  focal_point: number;
  placement_fit: number;
  contrast: number;
}

export const CRITERIA = ["style_cohesion", "focal_point", "placement_fit", "contrast"] as const;
export type Criterion = (typeof CRITERIA)[number];

export interface DesignDetail {
  design_id: string | null;
  run_id: string;
  render: { file_url: string | null; model_used: string | null; colorways_valid: string[] };
  qc: {
    scores: QcScores | null;
    pass_threshold: number;
    result: string | null;
    failing: string[];
    rubric_version: number | null;
  } | null;
  placement: { front: string; back: string; sleeve: string } | null;
  colorways: (string | { base: string; contrast_pass: boolean })[];
  context: { brief: { subject?: string; text?: string; style?: string } | null };
}

export interface Calibration {
  design_id: string | null;
  run_id: string;
  rubric: { result: string | null };
  human_decisions: { status: string }[];
  agreement: boolean | null;
  note: string | null;
}

export interface Swatch {
  label: string;
  valid: boolean;
  reason: string | null;
}

/** Bar width % for a 0–100 score (numeric labels render alongside — no color-only encoding). */
export function barWidth(score: number): number {
  return Math.max(0, Math.min(100, score));
}

/** Valid vs invalid swatches: strings from the valid list pass; objects carry their own verdict. */
export function swatchStates(
  colorways: DesignDetail["colorways"],
  valid: string[],
): Swatch[] {
  return colorways.map((entry) => {
    if (typeof entry === "string") {
      const ok = valid.includes(entry);
      return { label: entry, valid: ok, reason: ok ? null : "contrast fail" };
    }
    return {
      label: entry.base,
      valid: entry.contrast_pass,
      reason: entry.contrast_pass ? null : "contrast fail",
    };
  });
}

export function agreementLabel(calibration: Calibration | null): string {
  if (!calibration) return "calibration unknown";
  if (calibration.agreement === true) return "human agrees with rubric";
  if (calibration.agreement === false) return "human disagrees with rubric";
  return "no human decision yet";
}

/** Regenerate and reject both require a note (feeds the next render prompt). */
export function decisionNoteValid(note: string): boolean {
  return note.trim().length > 0;
}
