// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { QcView } from "../components/qc/qc-view";
import type { Calibration, DesignDetail } from "../lib/designs";

afterEach(cleanup);

function design(): DesignDetail {
  return {
    design_id: "d-1",
    run_id: "run-1",
    render: { file_url: "runs/d-1/render.png", model_used: "riverflow-v2-pro", colorways_valid: ["black"] },
    qc: {
      scores: { style_cohesion: 88, focal_point: 92, placement_fit: 85, contrast: 40 },
      pass_threshold: 70,
      result: "fail",
      failing: ["contrast"],
      rubric_version: 1,
    },
    placement: { front: "chest", back: "none", sleeve: "none" },
    colorways: ["black", "white"],
    context: { brief: { subject: "Rocket" } },
  };
}

const CALIBRATION: Calibration = {
  design_id: "d-1",
  run_id: "run-1",
  rubric: { result: "fail" },
  human_decisions: [],
  agreement: null,
  note: "no human decision recorded yet — agreement is unknown, not agreement",
};

function renderView(overrides: Partial<Parameters<typeof QcView>[0]> = {}) {
  return render(
    <QcView
      design={design()}
      calibration={CALIBRATION}
      renderSrc="/api/designs/run-1/render"
      canDecide
      deciding={null}
      error={null}
      onDecide={() => {}}
      {...overrides}
    />,
  );
}

describe("QcView", () => {
  it("renders raw numeric scores with the threshold", () => {
    renderView();
    expect(screen.getByText("88/100 pass")).toBeTruthy();
    expect(screen.getByText("40/100 fail")).toBeTruthy();
    expect(screen.getByText(/threshold 70/)).toBeTruthy();
  });

  it("shows valid vs invalid swatches with reasons", () => {
    renderView();
    expect(screen.getByText("black ✓")).toBeTruthy();
    expect(screen.getByText("white ✗ contrast fail")).toBeTruthy();
  });

  it("reject requires a note, approve does not", () => {
    const onDecide = vi.fn();
    renderView({ onDecide });
    fireEvent.click(screen.getByText("Reject"));
    expect(onDecide).not.toHaveBeenCalled();
    expect(screen.getByText(/reject needs a note/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("QC decision note"), { target: { value: "fix it" } });
    fireEvent.click(screen.getByText("Reject"));
    expect(onDecide).toHaveBeenCalledWith("reject", "fix it");
    fireEvent.click(screen.getByText("Approve"));
    expect(onDecide).toHaveBeenCalledWith("approve", "fix it");
  });

  it("regenerate carries the edited note", () => {
    const onDecide = vi.fn();
    renderView({ onDecide });
    fireEvent.change(screen.getByLabelText("QC decision note"), { target: { value: "mono-line only" } });
    fireEvent.click(screen.getByText("Regenerate"));
    expect(onDecide).toHaveBeenCalledWith("regenerate", "mono-line only");
  });

  it("shows the calibration indicator", () => {
    renderView();
    expect(screen.getByText("no human decision yet")).toBeTruthy();
    renderView({ calibration: { ...CALIBRATION, agreement: false } });
    expect(screen.getByText("human disagrees with rubric")).toBeTruthy();
  });

  it("serves the render from the same-origin API path", () => {
    renderView();
    const img = screen.getByAltText("Render for d-1") as HTMLImageElement;
    expect(img.getAttribute("src")).toBe("/api/designs/run-1/render");
  });
});
