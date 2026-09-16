// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, within, waitFor } from "@testing-library/react";

import { RosterTable } from "../components/agents/roster-table";

afterEach(cleanup);

const fakeAgents = [
  { node: "trend_research", role: "Trend Research", model: "google/gemini-2.0-flash-001", cap_usd: 50, spend_usd: 0, routing_edit: "pipeline/routing.py" },
  { node: "contract_approval", role: "Contract Approval", model: "anthropic/claude-sonnet-4-6", cap_usd: 50, spend_usd: 12.5, routing_edit: "pipeline/routing.py" },
  { node: "placement", role: "Placement", model: null, cap_usd: 50, spend_usd: 0, routing_edit: "pipeline/routing.py" },
];

describe("RosterTable", () => {
  it("shows loading state initially", () => {
    render(<RosterTable role="admin" />);
    expect(screen.getByText("Loading agents...")).toBeTruthy();
  });

  it("renders roster table after load", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(fakeAgents),
      }),
    );
    render(<RosterTable role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("trend_research")).toBeTruthy();
      expect(screen.getByText("contract_approval")).toBeTruthy();
      expect(screen.getByText("placement")).toBeTruthy();
    });
  });

  it("shows deterministic italic label for null model", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(fakeAgents),
      }),
    );
    render(<RosterTable role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("placement")).toBeTruthy();
    });
    expect(screen.getByText("deterministic")).toBeTruthy();
  });

  it("shows model name for non-null model", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(fakeAgents),
      }),
    );
    render(<RosterTable role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("google/gemini-2.0-flash-001")).toBeTruthy();
    });
  });

  it("renders cap and spend values", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(fakeAgents),
      }),
    );
    render(<RosterTable role="admin" />);
    await waitFor(() => {
      const cells50 = screen.getAllByText("$50.00");
      expect(cells50.length).toBeGreaterThanOrEqual(3);
      expect(screen.getByText("$12.50")).toBeTruthy();
    });
  });

  it("shows Edit buttons for admin role", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(fakeAgents),
      }),
    );
    render(<RosterTable role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("trend_research")).toBeTruthy();
    });
    const editButtons = screen.getAllByText("Edit").filter((el) => el.tagName === "BUTTON");
    expect(editButtons.length).toBe(3);
  });

  it("does not show Edit buttons for viewer role", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(fakeAgents),
      }),
    );
    render(<RosterTable role="viewer" />);
    await waitFor(() => {
      expect(screen.getByText("trend_research")).toBeTruthy();
    });
    const editButtons = screen.queryAllByRole("button", { name: "Edit" });
    expect(editButtons.length).toBe(0);
  });

  it("opens edit form on Edit click", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(fakeAgents),
      }),
    );
    render(<RosterTable role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("trend_research")).toBeTruthy();
    });
    const editButtons = screen.getAllByText("Edit").filter((el) => el.tagName === "BUTTON");
    fireEvent.click(editButtons[0]);
    expect(screen.getByPlaceholderText("Cap $")).toBeTruthy();
    expect(screen.getByPlaceholderText("Cost-impact note")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeTruthy();
  });

  it("shows error when cost-impact note is empty", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(fakeAgents),
      }),
    );
    render(<RosterTable role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("trend_research")).toBeTruthy();
    });
    const editButtons = screen.getAllByText("Edit").filter((el) => el.tagName === "BUTTON");
    fireEvent.click(editButtons[0]);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Cost-impact note is required")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// PBI-041: model picker, params, enabled toggle
// ---------------------------------------------------------------------------

const fullAgents = [
  { node: "trend_research", role: "Trend Research", model: "google/gemini-3.5-flash-lite", model_source: "store", params: { temperature: 0.7 }, enabled: true, overridden: ["model", "params"], prompt_key: "trend_clustering", prompt_version: "abc123", has_prompt_override: false, cap_usd: 50, spend_usd: 0, routing_edit: "pipeline/routing.py" },
  { node: "placement", role: "Placement", model: null, model_source: "default", params: {}, enabled: true, overridden: [], prompt_key: null, prompt_version: null, has_prompt_override: false, cap_usd: 50, spend_usd: 0, routing_edit: "pipeline/routing.py" },
];

const catalog = {
  models: [
    { id: "google/gemini-3.5-flash-lite", name: "Gemini 3.5 Flash Lite", context_length: 1000000, prompt_price_per_m: 0.3, completion_price_per_m: 2.5, input_modalities: ["text", "image"] },
    { id: "openai/gpt-5-image-mini", name: "GPT 5 Image Mini", context_length: 128000, prompt_price_per_m: 0.5, completion_price_per_m: 3.0, input_modalities: ["text", "image"] },
  ],
  stale: false,
  unavailable: false,
};

/** Route GETs to roster vs catalog vs prompt meta; record PATCH bodies. */
function mockAgentApi(opts?: {
  catalogResponse?: unknown;
  failModels?: boolean;
  promptMeta?: Record<string, unknown>;
}) {
  const calls: { url: string; body: unknown }[] = [];
  const catalogResponse = opts?.catalogResponse ?? catalog;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        calls.push({ url, body });
        const node = url.split("/api/agents/")[1].split("/config")[0];
        const before = fullAgents.find((a) => a.node === node) ?? fullAgents[0];
        // The real API never echoes prompt text or the note back.
        const { prompt_override: _po, cost_impact_note: _note, ...rest } = body;
        const merged: Record<string, unknown> = { ...before, ...rest };
        if (body.params === null) merged.params = {};
        if (body.prompt_override !== undefined) {
          merged.has_prompt_override = body.prompt_override !== null;
          merged.prompt_version = body.prompt_override === null ? "abc123" : "newver123";
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve(merged) });
      }
      if (url.includes("/api/agents/models")) {
        if (opts?.failModels) {
          return Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({}) });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve(catalogResponse) });
      }
      const promptMatch = url.match(/\/api\/agents\/([^/]+)\/prompt/);
      if (promptMatch) {
        const node = promptMatch[1];
        if (opts?.promptMeta) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(opts.promptMeta) });
        }
        const agent = fullAgents.find((a) => a.node === node);
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              node,
              prompt_key: agent?.prompt_key ?? null,
              base_version: agent?.prompt_key ? "v1" : null,
              prompt_version: agent?.prompt_version ?? null,
              has_override: agent?.has_prompt_override ?? false,
              override_chars: 0,
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(fullAgents) });
    }),
  );
  return calls;
}

async function openFirstEditor() {
  render(<RosterTable role="admin" />);
  await waitFor(() => {
    expect(screen.getByText("trend_research")).toBeTruthy();
  });
  const editButtons = screen.getAllByText("Edit").filter((el) => el.tagName === "BUTTON");
  fireEvent.click(editButtons[0]);
  await waitFor(() => {
    expect(screen.getByPlaceholderText("Search models…")).toBeTruthy();
  });
}

describe("RosterTable agent control plane", () => {
  it("marks overridden vs default models and shows params", async () => {
    mockAgentApi();
    render(<RosterTable role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("overridden")).toBeTruthy();
      expect(screen.getByText("t=0.7")).toBeTruthy();
      expect(screen.getAllByText("enabled").length).toBeGreaterThanOrEqual(2);
    });
  });

  it("picker renders catalog rows with price and modalities", async () => {
    mockAgentApi();
    await openFirstEditor();
    await waitFor(() => {
      const options = within(screen.getByRole("listbox")).getAllByRole("option");
      expect(options.length).toBe(2);
    });
    // Price per M and modalities are visible at the point of choosing.
    const listbox = screen.getByRole("listbox");
    expect(within(listbox).getAllByText(/per M/).length).toBeGreaterThanOrEqual(2);
    expect(within(listbox).getAllByText(/text, image/).length).toBeGreaterThanOrEqual(2);
  });

  it("search filters the picker through ?q=", async () => {
    const calls = mockAgentApi();
    await openFirstEditor();
    await waitFor(() => {
      expect(screen.getByText("openai/gpt-5-image-mini")).toBeTruthy();
    });
    const search = screen.getByPlaceholderText("Search models…");
    fireEvent.change(search, { target: { value: "gpt-5" } });
    await waitFor(() => {
      const qs = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls
        .map(([url]: [string]) => String(url))
        .filter((u) => u.includes("/api/agents/models"));
      expect(qs.some((u) => u.includes("q=gpt-5"))).toBe(true);
    });
    expect(calls).toBeDefined();
  });

  it("an unknown model can never be offered: no matches, no options", async () => {
    mockAgentApi({ catalogResponse: { models: [], stale: false, unavailable: false } });
    await openFirstEditor();
    await waitFor(() => {
      expect(screen.getByText("No matching models — refine the search.")).toBeTruthy();
    });
    expect(screen.queryByRole("option")).toBeNull();
  });

  it("enabled toggle saves with a note and surfaces the diff", async () => {
    const calls = mockAgentApi();
    await openFirstEditor();
    const checkbox = screen.getByLabelText(/Enabled —/) as HTMLInputElement;
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(false);
    fireEvent.change(screen.getByPlaceholderText("Cost-impact note"), {
      target: { value: "pause trend spend" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(screen.getByTestId("save-diff")).toBeTruthy();
    });
    expect(screen.getByTestId("save-diff").textContent).toContain("enabled true → false");
    const patch = calls.find((c) => c.url.includes("/config"));
    expect(patch).toBeTruthy();
    expect(patch!.body).toMatchObject({ enabled: false, cost_impact_note: "pause trend spend" });
  });

  it("unavailable catalog disables the picker with a reason", async () => {
    mockAgentApi({ catalogResponse: { models: [], stale: false, unavailable: true } });
    await openFirstEditor();
    await waitFor(() => {
      expect(screen.getByText(/Model catalog unavailable/)).toBeTruthy();
    });
    expect(screen.queryByPlaceholderText("Search models…")).toBeNull();
  });

  it("viewer sees params and status but no edit controls", async () => {
    mockAgentApi();
    render(<RosterTable role="viewer" />);
    await waitFor(() => {
      expect(screen.getByText("t=0.7")).toBeTruthy();
      expect(screen.getByText("overridden")).toBeTruthy();
    });
    expect(screen.queryAllByRole("button", { name: "Edit" }).length).toBe(0);
  });

  it("override toggle reveals the prompt editor with the live version", async () => {
    mockAgentApi();
    await openFirstEditor();
    await waitFor(() => {
      expect(screen.getByText(/Prompt: trend_clustering/)).toBeTruthy();
    });
    expect(screen.getByText(/version abc123/)).toBeTruthy();
    // Toggle off by default (no override) → no textarea until enabled.
    expect(screen.queryByLabelText("Prompt override")).toBeNull();
    fireEvent.click(screen.getByLabelText("Override the built-in prompt"));
    expect(screen.getByLabelText("Prompt override")).toBeTruthy();
  });

  it("saving an override sends text and surfaces the version diff", async () => {
    const calls = mockAgentApi();
    await openFirstEditor();
    fireEvent.click(screen.getByLabelText("Override the built-in prompt"));
    fireEvent.change(screen.getByLabelText("Prompt override"), {
      target: { value: "Cluster strictly by color." },
    });
    fireEvent.change(screen.getByPlaceholderText("Cost-impact note"), {
      target: { value: "tighter clusters" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(screen.getByTestId("save-diff")).toBeTruthy();
    });
    expect(screen.getByTestId("save-diff").textContent).toContain("prompt abc123 → newver123");
    const patch = calls.find((c) => c.url.includes("/config"));
    expect(patch).toBeTruthy();
    expect(patch!.body).toMatchObject({ prompt_override: "Cluster strictly by color." });
  });

  it("clearing an override sends null and restores built-in", async () => {
    const calls = mockAgentApi({
      promptMeta: { node: "trend_research", prompt_key: "trend_clustering", base_version: "v1", prompt_version: "ovr123", has_override: true, override_chars: 24 },
    });
    await openFirstEditor();
    await waitFor(() => {
      expect(screen.getByText("Use built-in (clear override)")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Use built-in (clear override)"));
    fireEvent.change(screen.getByPlaceholderText("Cost-impact note"), {
      target: { value: "revert to built-in" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(screen.getByTestId("save-diff")).toBeTruthy();
    });
    const patch = calls.find((c) => c.url.includes("/config"));
    expect(patch!.body).toMatchObject({ prompt_override: null });
  });

  it("deterministic nodes offer no prompt section", async () => {
    mockAgentApi();
    render(<RosterTable role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("placement")).toBeTruthy();
    });
    const editButtons = screen.getAllByText("Edit").filter((el) => el.tagName === "BUTTON");
    fireEvent.click(editButtons[1]);
    await waitFor(() => {
      expect(screen.getByText(/Deterministic node/)).toBeTruthy();
    });
    expect(screen.queryByLabelText("Override the built-in prompt")).toBeNull();
    expect(screen.queryByText(/Prompt:/)).toBeNull();
  });
});
