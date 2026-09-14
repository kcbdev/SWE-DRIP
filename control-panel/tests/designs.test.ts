import { describe, expect, it } from "vitest";

import {
  agreementLabel,
  barWidth,
  decisionNoteValid,
  swatchStates,
} from "../lib/designs";

describe("design-qc helpers", () => {
  it("clamps bar widths", () => {
    expect(barWidth(88)).toBe(88);
    expect(barWidth(140)).toBe(100);
    expect(barWidth(-3)).toBe(0);
  });

  it("marks valid vs invalid swatches with reasons", () => {
    const swatches = swatchStates(["black", "white", { base: "gray", contrast_pass: false }], ["black"]);
    expect(swatches[0]).toEqual({ label: "black", valid: true, reason: null });
    expect(swatches[1]).toEqual({ label: "white", valid: false, reason: "contrast fail" });
    expect(swatches[2]).toEqual({ label: "gray", valid: false, reason: "contrast fail" });
  });

  it("labels calibration states", () => {
    expect(agreementLabel(null)).toBe("calibration unknown");
    expect(
      agreementLabel({ design_id: "d", run_id: "r", rubric: { result: "pass" }, human_decisions: [], agreement: null, note: null }),
    ).toBe("no human decision yet");
    expect(
      agreementLabel({ design_id: "d", run_id: "r", rubric: { result: "pass" }, human_decisions: [], agreement: true, note: null }),
    ).toBe("human agrees with rubric");
    expect(
      agreementLabel({ design_id: "d", run_id: "r", rubric: { result: "pass" }, human_decisions: [], agreement: false, note: null }),
    ).toBe("human disagrees with rubric");
  });

  it("requires notes for reject/regenerate decisions", () => {
    expect(decisionNoteValid("  ")).toBe(false);
    expect(decisionNoteValid("fix the focal point")).toBe(true);
  });
});
