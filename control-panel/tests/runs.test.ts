import { describe, expect, it } from "vitest";

import {
  NODE_ORDER,
  flowStates,
  formatDuration,
  nodeDurations,
  nodeSetMismatch,
  prettyState,
  trackerStates,
  type RunDetail,
} from "../lib/runs";

function detail(status: string, reached: string[]): RunDetail {
  return {
    id: "run-1",
    collection_id: "vibe",
    design_id: "d-1",
    status,
    current_node: reached[reached.length - 1] ?? null,
    started_at: null,
    updated_at: null,
    nodes: NODE_ORDER.map((node) => ({
      node,
      reached: reached.includes(node),
      state: reached.includes(node) ? { ran: true } : null,
      at: null,
    })),
    errors: [],
  };
}

describe("runs helpers", () => {
  it("renders all 11 nodes in locked order", () => {
    expect(NODE_ORDER).toHaveLength(11);
    expect(detail("running", ["trend_research"]).nodes.map((n) => n.node)).toEqual([...NODE_ORDER]);
  });

  it("marks current vs complete vs pending", () => {
    const states = trackerStates(detail("running", ["trend_research", "contract_approval"]));
    expect(states[0]).toEqual({ node: "trend_research", state: "complete" });
    expect(states[1]).toEqual({ node: "contract_approval", state: "current" });
    expect(states[2]).toEqual({ node: "listing_copy", state: "pending" });
  });

  it("marks the furthest node failed on failed runs", () => {
    const states = trackerStates(detail("failed", ["trend_research"]));
    expect(states[0].state).toBe("failed");
  });

  it("flags node-set divergence loudly", () => {
    const d = detail("running", ["trend_research"]);
    expect(nodeSetMismatch(d.nodes)).toEqual([]);
    expect(nodeSetMismatch(d.nodes.slice(1))).toContain("missing: trend_research");
    expect(nodeSetMismatch([...d.nodes, { node: "nope", reached: true, state: null, at: null }])).toContain(
      "extra: nope",
    );
  });

  it("pretty-prints state with affordances", () => {
    expect(prettyState(null)).toBe("—");
    expect(prettyState({ a: 1 })).toContain('"a": 1');
  });
});

describe("flow states (PBI-042)", () => {
  it("covers complete / current / awaiting-approval / failed / not-reached", () => {
    const awaiting = flowStates(detail("awaiting_approval", ["trend_research", "contract_approval"]));
    expect(awaiting[0]).toEqual({ node: "trend_research", state: "complete" });
    expect(awaiting[1]).toEqual({ node: "contract_approval", state: "awaiting-approval" });
    expect(awaiting[2]).toEqual({ node: "listing_copy", state: "not-reached" });

    const failed = flowStates(detail("failed", ["trend_research"]));
    expect(failed[0]).toEqual({ node: "trend_research", state: "failed" });

    const running = flowStates(detail("running", ["trend_research"]));
    expect(running[0]).toEqual({ node: "trend_research", state: "current" });

    const complete = flowStates(detail("complete", [...NODE_ORDER]));
    expect(complete.slice(0, 10).every((s) => s.state === "complete")).toBe(true);
    expect(complete[10]).toEqual({ node: "shelf", state: "current" });
  });
});

describe("node durations", () => {
  it("measures first-to-last per node, null when unobserved", () => {
    const durations = nodeDurations([
      { node: "trend_research", level: "info", message: "a", detail: {}, ts: "2026-09-16T00:00:00+00:00" },
      { node: "trend_research", level: "info", message: "b", detail: {}, ts: "2026-09-16T00:00:30+00:00" },
      { node: "shelf", level: "info", message: "once", detail: {}, ts: "2026-09-16T00:01:00+00:00" },
      { node: "shelf", level: "info", message: "bad-ts", detail: {}, ts: "not-a-time" },
    ]);
    expect(durations["trend_research"]).toBe(30);
    expect(durations["shelf"]).toBeNull();
    expect(durations["placement"]).toBeUndefined();
  });

  it("formats durations readably", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(0.5)).toBe("0.5s");
    expect(formatDuration(30)).toBe("30s");
    expect(formatDuration(184)).toBe("3m 04s");
  });
});
