import { describe, expect, it } from "vitest";

import {
  detailHrefFor,
  filterByTab,
  rejectNoteValid,
  tabFor,
  waitingAge,
  type ApprovalItem,
} from "../lib/approvals";

function item(id: number, node: string): ApprovalItem {
  return {
    id,
    run_id: `run-${id}`,
    node,
    status: "pending",
    payload: {},
    entity_ref: { type: "x", id: null, label: `Item ${id}` },
    waiting_since: "2026-09-14T10:00:00.000Z",
  };
}

describe("approvals helpers", () => {
  it("classifies nodes into tabs", () => {
    expect(tabFor(item(1, "contract_approval"))).toBe("collections");
    expect(tabFor(item(2, "aesthetic_qc"))).toBe("designs");
    expect(tabFor(item(3, "publish_gate"))).toBe("publishes");
  });

  it("filters rows per tab", () => {
    const rows = [item(1, "contract_approval"), item(2, "publish_gate")];
    expect(filterByTab(rows, "all")).toHaveLength(2);
    expect(filterByTab(rows, "collections")).toHaveLength(1);
    expect(filterByTab(rows, "designs")).toHaveLength(0);
  });

  it("formats waiting ages", () => {
    const now = new Date("2026-09-14T12:00:00.000Z").getTime();
    expect(waitingAge("2026-09-14T11:50:00.000Z", now)).toBe("10m");
    expect(waitingAge("2026-09-14T09:00:00.000Z", now)).toBe("3h");
    expect(waitingAge(null, now)).toBe("—");
  });

  it("requires a note to reject", () => {
    expect(rejectNoteValid("  ")).toBe(false);
    expect(rejectNoteValid("off-brand")).toBe(true);
  });

  it("has no detail routes until gate screens land", () => {
    expect(detailHrefFor(item(1, "contract_approval"))).toBeNull();
  });
});
