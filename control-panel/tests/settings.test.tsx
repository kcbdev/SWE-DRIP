// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";

import { HitlToggles } from "../components/settings/hitl-toggles";
import { BrandConstantsView } from "../components/settings/brand-constants";
import { IntegrationsStatus } from "../components/settings/integrations-status";

afterEach(cleanup);

// ---------------------------------------------------------------------------
// HitlToggles
// ---------------------------------------------------------------------------

describe("HitlToggles", () => {
  it("shows loading state initially", () => {
    render(<HitlToggles role="admin" />);
    expect(screen.getByText("Loading HITL flags...")).toBeTruthy();
  });

  it("renders node toggles after load", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ contract_approval: true, aesthetic_qc: false }),
      }),
    );
    render(<HitlToggles role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("contract_approval")).toBeTruthy();
      expect(screen.getByText("aesthetic_qc")).toBeTruthy();
    });
    expect(screen.getByText("ON")).toBeTruthy();
    expect(screen.getByText("OFF")).toBeTruthy();
  });

  it("shows ON/OFF labels for viewer role (no toggle buttons)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ contract_approval: true }),
      }),
    );
    render(<HitlToggles role="viewer" />);
    await waitFor(() => {
      expect(screen.getByText("contract_approval")).toBeTruthy();
    });
    // Viewer sees the status label, not a button
    const onLabel = screen.getByText("ON");
    expect(onLabel.tagName.toLowerCase()).not.toBe("button");
  });

  it("shows confirmation dialog on toggle click", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ contract_approval: true }),
      }),
    );
    render(<HitlToggles role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("contract_approval")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("ON"));
    expect(screen.getByText("Confirm disable?")).toBeTruthy();
    expect(screen.getByText("Yes")).toBeTruthy();
    expect(screen.getByText("Cancel")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// BrandConstantsView
// ---------------------------------------------------------------------------

describe("BrandConstantsView", () => {
  it("shows loading state initially", () => {
    render(<BrandConstantsView role="admin" />);
    expect(screen.getByText("Loading brand constants...")).toBeTruthy();
  });

  it("renders palette, typeface, and forbidden elements", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            palette: { void_black: "#0D0D0D", terminal_green: "#00FF41" },
            typeface: "JetBrains Mono",
            forbidden: ["gradients", "shadows"],
          }),
      }),
    );
    render(<BrandConstantsView role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("Palette")).toBeTruthy();
      expect(screen.getByText(/void_black/)).toBeTruthy();
      expect(screen.getByText(/terminal_green/)).toBeTruthy();
      expect(screen.getByText("JetBrains Mono")).toBeTruthy();
      expect(screen.getByText("gradients")).toBeTruthy();
      expect(screen.getByText("shadows")).toBeTruthy();
    });
  });
});

// ---------------------------------------------------------------------------
// IntegrationsStatus
// ---------------------------------------------------------------------------

describe("IntegrationsStatus", () => {
  it("shows loading state initially", () => {
    render(<IntegrationsStatus />);
    expect(screen.getByText("Loading integrations...")).toBeTruthy();
  });

  it("renders configured/not-configured status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            fourthwall_mcp: true,
            openrouter: false,
            fourthwall_mcp_url: "",
            openrouter_base_url: "https://openrouter.ai/api/v1",
          }),
      }),
    );
    render(<IntegrationsStatus />);
    await waitFor(() => {
      expect(screen.getByText("Fourthwall MCP")).toBeTruthy();
      expect(screen.getByText("OpenRouter API Key")).toBeTruthy();
    });
    const configured = screen.getByText("Configured");
    const notConfigured = screen.getByText("Not configured");
    expect(configured).toBeTruthy();
    expect(notConfigured).toBeTruthy();
  });

  it("hides the credential form for non-admins", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            fourthwall_mcp: false,
            openrouter: false,
            fourthwall_mcp_url: "",
            openrouter_base_url: "https://openrouter.ai/api/v1",
          }),
      }),
    );
    render(<IntegrationsStatus role="viewer" />);
    await waitFor(() => expect(screen.getByText("Fourthwall MCP")).toBeTruthy());
    expect(screen.queryByText("Set credentials")).toBeNull();
  });

  it("lets admins set credentials and test the connection", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          fourthwall_mcp: false,
          openrouter: false,
          fourthwall_mcp_url: "",
          openrouter_base_url: "https://openrouter.ai/api/v1",
        }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<IntegrationsStatus role="admin" />);
    await waitFor(() => expect(screen.getByText("Set credentials")).toBeTruthy());

    fireEvent.change(screen.getByLabelText(/OpenRouter API key/i), {
      target: { value: "openrouter-test-key" },
    });
    fireEvent.click(screen.getByText("Save credentials"));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === "PATCH",
      );
      expect(patchCall).toBeTruthy();
      expect((patchCall![1] as RequestInit).body).toContain("openrouter-test-key");
    });
  });
});
