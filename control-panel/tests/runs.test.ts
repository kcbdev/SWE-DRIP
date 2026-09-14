import { describe, expect, it } from "vitest";

import {
  NODE_ORDER,
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
