// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { RunDetailView } from "../components/runs/run-detail-view";
import { NODE_ORDER, type RunDetail } from "../lib/runs";

afterEach(cleanup);

function detail(): RunDetail {
  return {
    id: "run-1",
    collection_id: "vibe",
    design_id: "d-1",
    status: "awaiting_approval",
    current_node: "contract_approval",
    started_at: null,
    updated_at: null,
    nodes: NODE_ORDER.map((node) => ({
      node,
      reached: ["trend_research", "contract_approval"].includes(node),
      state: ["trend_research", "contract_approval"].includes(node) ? { ran: true } : null,
      at: null,
    })),
    errors: [],
  };
}

function renderView(overrides: Partial<Parameters<typeof RunDetailView>[0]> = {}) {
  return render(
    <RunDetailView detail={detail()} canReplay replaying={null} error={null} onReplay={() => {}} {...overrides} />,
  );
}

describe("RunDetailView", () => {
  it("renders the 11-node tracker in order", () => {
    renderView();
    for (const node of NODE_ORDER) {
      expect(screen.getByTitle(`${node}: ${["trend_research"].includes(node) ? "complete" : node === "contract_approval" ? "current" : "pending"}`)).toBeTruthy();
    }
  });

  it("opens a node panel with recorded state", () => {
    renderView();
    fireEvent.click(screen.getByTitle("contract_approval: current"));
    expect(screen.getByText(/"ran": true/)).toBeTruthy();
  });

  it("replay requires confirmation and shows pending", () => {
    const onReplay = vi.fn();
    renderView({ onReplay });
    fireEvent.click(screen.getByTitle("contract_approval: current"));
    fireEvent.click(screen.getByText("Replay from here"));
    expect(onReplay).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Confirm replay"));
    expect(onReplay).toHaveBeenCalledWith("contract_approval");
    cleanup();
    renderView({ onReplay, replaying: "contract_approval" });
    fireEvent.click(screen.getByTitle("contract_approval: current"));
    fireEvent.click(screen.getByText("Replay from here"));
    expect(screen.getByText("replaying…")).toBeTruthy();
  });

  it("warns loudly on node-set mismatch", () => {
    const bad = detail();
    bad.nodes = bad.nodes.slice(1);
    renderView({ detail: bad });
    expect(screen.getByText(/Node set mismatch/)).toBeTruthy();
  });

  it("hides replay from viewers", () => {
    renderView({ canReplay: false });
    fireEvent.click(screen.getByTitle("contract_approval: current"));
    expect(screen.queryByText("Replay from here")).toBeNull();
  });
});
