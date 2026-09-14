import { afterEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Agent types + API helpers
// ---------------------------------------------------------------------------

// We test the shape and type contracts by importing and mocking fetch.

import { fetchAgents, fetchAgentDetail, patchAgentCap } from "../lib/agents";

function mockFetch(json: unknown, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      json: () => Promise.resolve(json),
    }),
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("agents API helpers", () => {
  it("fetchAgents returns array of agents", async () => {
    mockFetch([
      { node: "trend_research", role: "Trend Research", model: "gemini", cap_usd: 50, spend_usd: 0, routing_edit: "pipeline/routing.py" },
    ]);
    const agents = await fetchAgents();
    expect(Array.isArray(agents)).toBe(true);
    expect(agents[0].node).toBe("trend_research");
    expect(agents[0].cap_usd).toBe(50);
  });

  it("fetchAgentDetail returns single agent", async () => {
    mockFetch({ node: "contract_approval", role: "Contract Approval", model: "claude", cap_usd: 50, spend_usd: 0, routing_edit: "pipeline/routing.py" });
    const agent = await fetchAgentDetail("contract_approval");
    expect(agent.node).toBe("contract_approval");
  });

  it("patchAgentCap sends PATCH with body", async () => {
    mockFetch({ node: "contract_approval", role: "Contract Approval", model: "claude", cap_usd: 75, spend_usd: 0, routing_edit: "pipeline/routing.py" });
    const result = await patchAgentCap("contract_approval", 75, "QA increase");
    expect(result.cap_usd).toBe(75);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/contract_approval/config"),
      expect.objectContaining({ method: "PATCH" }),
    );
  });
});
