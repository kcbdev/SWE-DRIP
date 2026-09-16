// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { RunDetailView } from "../components/runs/run-detail-view";
import { RunsList } from "../components/runs/runs-list";
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
    <RunDetailView
      detail={detail()}
      logs={[]}
      canReplay
      replaying={null}
      error={null}
      onReplay={() => {}}
      onRefreshLogs={() => {}}
      {...overrides}
    />,
  );
}

describe("RunDetailView", () => {
  it("renders the 11-node flow in order with status colours", () => {
    renderView();
    for (const node of NODE_ORDER) {
      expect(screen.getByTitle(`${node}: ${["trend_research"].includes(node) ? "complete" : node === "contract_approval" ? "awaiting-approval" : "not-reached"}`)).toBeTruthy();
    }
  });

  it("marks the gate node awaiting-approval and failures failed", () => {
    const awaiting = detail();
    awaiting.status = "awaiting_approval";
    render(
      <RunDetailView
        detail={awaiting}
        logs={[]}
        canReplay
        replaying={null}
        error={null}
        onReplay={() => {}}
        onRefreshLogs={() => {}}
      />,
    );
    expect(screen.getByTitle("contract_approval: awaiting-approval")).toBeTruthy();
    cleanup();
    const failed = detail();
    failed.status = "failed";
    render(
      <RunDetailView
        detail={failed}
        logs={[]}
        canReplay
        replaying={null}
        error={null}
        onReplay={() => {}}
        onRefreshLogs={() => {}}
      />,
    );
    expect(screen.getByTitle("contract_approval: failed")).toBeTruthy();
  });

  it("opens a node panel with recorded state", () => {
    renderView();
    fireEvent.click(screen.getByTitle("contract_approval: awaiting-approval"));
    expect(screen.getByText(/"ran": true/)).toBeTruthy();
  });

  it("replay requires confirmation and shows pending", () => {
    const onReplay = vi.fn();
    renderView({ onReplay });
    fireEvent.click(screen.getByTitle("contract_approval: awaiting-approval"));
    fireEvent.click(screen.getByText("Replay from here"));
    expect(onReplay).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Confirm replay"));
    expect(onReplay).toHaveBeenCalledWith("contract_approval");
    cleanup();
    renderView({ onReplay, replaying: "contract_approval" });
    fireEvent.click(screen.getByTitle("contract_approval: awaiting-approval"));
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
    fireEvent.click(screen.getByTitle("contract_approval: awaiting-approval"));
    expect(screen.queryByText("Replay from here")).toBeNull();
  });

  it("logs tab shows the failed node's reason without container logs", () => {
    const failed = detail();
    failed.status = "failed";
    render(
      <RunDetailView
        detail={failed}
        logs={[
          { node: "contract_approval", level: "error", message: "resume decision missing or unknown approved_cluster_id ('c-9')", detail: {}, ts: "2026-09-16T00:00:01+00:00" },
          { node: "contract_approval", level: "info", message: "2 drafts awaiting approval", detail: {}, ts: "2026-09-16T00:00:00+00:00" },
        ]}
        canReplay
        replaying={null}
        error={null}
        onReplay={() => {}}
        onRefreshLogs={() => {}}
      />,
    );
    fireEvent.click(screen.getByTitle("contract_approval: failed"));
    fireEvent.click(screen.getByRole("tab", { name: /logs \(2\)/ }));
    expect(screen.getByText(/resume decision missing/)).toBeTruthy();
  });

  it("shows per-node durations from log timestamps", () => {
    renderView({
      logs: [
        { node: "trend_research", level: "info", message: "start", detail: {}, ts: "2026-09-16T00:00:00+00:00" },
        { node: "trend_research", level: "info", message: "done", detail: {}, ts: "2026-09-16T00:00:30+00:00" },
      ],
    });
    expect(screen.getByTitle("trend_research: complete").textContent).toContain("30s");
  });

  it("shows the resolved run config per node", () => {
    const d = detail();
    d.node_config = {
      contract_approval: { model: "anthropic/claude-sonnet-5", params: {}, enabled: true },
    };
    renderView({ detail: d });
    fireEvent.click(screen.getByTitle("contract_approval: awaiting-approval"));
    expect(screen.getByText(/run config: anthropic\/claude-sonnet-5/)).toBeTruthy();
  });
});

describe("RunsList search and filters", () => {
  const items = [
    { id: "run-1", collection_id: "vibe-coding", design_id: "d-1", status: "complete", current_node: "shelf", started_at: "2026-09-16T10:00:00+00:00", updated_at: "2026-09-16T10:05:00+00:00" },
    { id: "run-2", collection_id: "other", design_id: "d-2", status: "failed", current_node: "shelf", started_at: "2026-09-15T10:00:00+00:00", updated_at: "2026-09-15T10:05:00+00:00" },
  ];

  it("search matches run, design or collection substrings", () => {
    render(<RunsList items={items} />);
    fireEvent.change(screen.getByPlaceholderText("run, design or collection…"), {
      target: { value: "vibe" },
    });
    expect(screen.getByText("d-1")).toBeTruthy();
    expect(screen.queryByText("d-2")).toBeNull();
  });

  it("date filter matches the start day", () => {
    render(<RunsList items={items} />);
    fireEvent.change(screen.getByLabelText(/Date/), { target: { value: "2026-09-15" } });
    expect(screen.getByText("d-2")).toBeTruthy();
    expect(screen.queryByText("d-1")).toBeNull();
  });
});
