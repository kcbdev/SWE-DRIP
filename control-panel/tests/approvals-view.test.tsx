// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { ApprovalsView } from "../components/approvals/approvals-view";
import type { ApprovalItem } from "../lib/approvals";

afterEach(cleanup);

const ROWS: ApprovalItem[] = [
  {
    id: 1,
    run_id: "run-1",
    node: "contract_approval",
    status: "pending",
    payload: {},
    entity_ref: { type: "collection_contract", id: "vibe-coding", label: "Vibe Coding" },
    waiting_since: "2026-09-14T10:00:00.000Z",
  },
  {
    id: 2,
    run_id: "run-2",
    node: "publish_gate",
    status: "pending",
    payload: {},
    entity_ref: { type: "product", id: "fw-1", label: "Vibe Tee" },
    waiting_since: "2026-09-14T11:00:00.000Z",
  },
];

function renderView(overrides: Partial<Parameters<typeof ApprovalsView>[0]> = {}) {
  return render(
    <ApprovalsView
      items={ROWS}
      canDecide
      deciding={{}}
      error={null}
      streamLive
      onDecide={() => {}}
      onRefresh={() => {}}
      {...overrides}
    />,
  );
}

describe("ApprovalsView", () => {
  it("filters rows by tab", () => {
    renderView();
    expect(screen.getByText("Vibe Coding")).toBeTruthy();
    fireEvent.click(screen.getByText("Publishes"));
    expect(screen.queryByText("Vibe Coding")).toBeNull();
    expect(screen.getByText("Vibe Tee")).toBeTruthy();
  });

  it("one-click approve calls through with an empty note", () => {
    const onDecide = vi.fn();
    renderView({ onDecide });
    fireEvent.click(screen.getAllByText("Approve")[0]);
    expect(onDecide).toHaveBeenCalledWith(ROWS[0], "approve", "");
  });

  it("reject requires a note", () => {
    const onDecide = vi.fn();
    renderView({ onDecide });
    fireEvent.click(screen.getAllByText("Reject")[0]);
    expect(onDecide).not.toHaveBeenCalled();
    expect(screen.getByText(/reject needs a note/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Note for approval 1"), {
      target: { value: "off-brand" },
    });
    fireEvent.click(screen.getAllByText("Reject")[0]);
    expect(onDecide).toHaveBeenCalledWith(ROWS[0], "reject", "off-brand");
  });

  it("shows the resuming pending state per row", () => {
    renderView({ deciding: { 1: "approve" } });
    expect(screen.getByText("resuming pipeline…")).toBeTruthy();
  });

  it("hides decide controls from viewers", () => {
    renderView({ canDecide: false });
    expect(screen.queryByText("Approve")).toBeNull();
    expect(screen.queryByText("Reject")).toBeNull();
  });

  it("flags an unavailable stream with manual refresh", () => {
    const onRefresh = vi.fn();
    renderView({ streamLive: false, onRefresh });
    expect(screen.getByText(/manual refresh/)).toBeTruthy();
    fireEvent.click(screen.getByText("Refresh"));
    expect(onRefresh).toHaveBeenCalled();
  });
});
