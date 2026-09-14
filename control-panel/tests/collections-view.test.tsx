// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { CollectionDetail } from "../components/collections/collection-detail";
import { CollectionsList } from "../components/collections/collections-list";
import type { CollectionRecord } from "../lib/collections";

afterEach(cleanup);

function record(overrides: Partial<CollectionRecord["contract"]> = {}): CollectionRecord {
  const collection_id = overrides.collection_id ?? "vibe-coding";
  return {
    id: collection_id,
    mtime: 0,
    contract: {
      collection_id,
      theme: "Vibe Coding",
      status: "draft",
      style_archetype: "terminal-brutalist",
      illustration_rules: { line_weight: "bold", palette: ["#00FF41"], no_mixed_styles: true },
      garment_colorways: [{ base: "black", contrast_pass: true }],
      placement_templates: [{ design_type: "hero-icon", front: "chest", back: "none", sleeve: "none" }],
      product_count_target: 6,
      lifecycle_days: 90,
      kpi_thresholds: { min_units: 5, min_conversion: 0.02, eval_window_days: 30 },
      created_by: "u-1",
      created_at: "2026-09-14T10:00:00.000Z",
      approved_at: null,
      retired_at: null,
      ...overrides,
    },
  };
}

describe("CollectionsList", () => {
  it("filters active / candidates / retired", () => {
    render(
      <CollectionsList
        items={[
          record({ collection_id: "a", theme: "A", status: "active" }),
          record({ collection_id: "d", theme: "D", status: "draft" }),
        ]}
        canCreate={false}
      />,
    );
    fireEvent.click(screen.getByText("Candidates"));
    expect(screen.queryByText("A")).toBeNull();
    expect(screen.getByText("D")).toBeTruthy();
  });
});

describe("CollectionDetail", () => {
  const base = { role: "admin", error: null, acting: false, onApprove: () => {}, onRetire: () => {} };

  it("renders palette chips and placement diagrams", () => {
    render(<CollectionDetail record={record()} {...base} />);
    expect(screen.getByText("#00FF41")).toBeTruthy();
    expect(screen.getByText("hero-icon")).toBeTruthy();
  });

  it("approve requires confirmation", () => {
    const onApprove = vi.fn();
    render(<CollectionDetail record={record()} {...base} onApprove={onApprove} />);
    fireEvent.click(screen.getByText("Approve"));
    expect(onApprove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Confirm approve"));
    expect(onApprove).toHaveBeenCalled();
  });

  it("retire collects survivors before confirming", () => {
    const onRetire = vi.fn();
    render(
      <CollectionDetail
        record={record({ status: "active" })}
        {...base}
        onRetire={onRetire}
      />,
    );
    fireEvent.click(screen.getByText("Retire…"));
    fireEvent.change(screen.getByLabelText("Survivor product ids"), { target: { value: "fw-1, fw-2" } });
    fireEvent.click(screen.getByText("Confirm retire"));
    expect(onRetire).toHaveBeenCalledWith(["fw-1", "fw-2"]);
  });

  it("shows the KPI empty-state slot", () => {
    render(<CollectionDetail record={record()} {...base} />);
    expect(screen.getByText(/No analytics yet/)).toBeTruthy();
  });

  it("hides lifecycle actions from viewers", () => {
    render(<CollectionDetail record={record({ status: "active" })} {...base} role="viewer" />);
    expect(screen.queryByText("Retire…")).toBeNull();
  });
});
