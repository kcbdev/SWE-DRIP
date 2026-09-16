import { afterEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Agent types + API helpers
// ---------------------------------------------------------------------------

// We test the shape and type contracts by importing and mocking fetch.

import { fetchAgents, fetchAgentDetail, patchAgentCap, fetchModels, fetchPromptMeta, patchAgentConfig } from "../lib/agents";

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

  it("fetchModels returns catalog rows with pricing and modalities", async () => {
    mockFetch({
      models: [
        { id: "google/gemini-3.5-flash-lite", name: "Gemini 3.5 Flash Lite", context_length: 1000000, prompt_price_per_m: 0.3, completion_price_per_m: 2.5, input_modalities: ["text", "image"] },
      ],
      stale: false,
      unavailable: false,
    });
    const list = await fetchModels("gemini");
    expect(list.models[0].id).toBe("google/gemini-3.5-flash-lite");
    expect(list.models[0].prompt_price_per_m).toBe(0.3);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/models?q=gemini"),
      expect.anything(),
    );
  });

  it("fetchPromptMeta returns key/version without text", async () => {
    mockFetch({ node: "aesthetic_qc", prompt_key: "qc_rubric", base_version: "v1", prompt_version: "e01d513a5ce4", has_override: false, override_chars: 0 });
    const meta = await fetchPromptMeta("aesthetic_qc");
    expect(meta.prompt_key).toBe("qc_rubric");
    expect(meta.prompt_version).toBe("e01d513a5ce4");
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/aesthetic_qc/prompt"),
      expect.anything(),
    );
  });
  it("patchAgentConfig sends model/params/enabled with the cost note", async () => {
    mockFetch({ node: "trend_research", model: "openai/gpt-5-image-mini", cap_usd: 50, spend_usd: 0, routing_edit: "pipeline/routing.py" });
    const result = await patchAgentConfig("trend_research", {
      model: "openai/gpt-5-image-mini",
      params: { temperature: 0.5 },
      enabled: false,
      cost_impact_note: "test run",
    });
    expect(result.model).toBe("openai/gpt-5-image-mini");
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/trend_research/config"),
      expect.objectContaining({
        method: "PATCH",
        body: expect.stringContaining("openai/gpt-5-image-mini"),
      }),
    );
  });
});
