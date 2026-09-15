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

const STATUS = {
  fourthwall: false,
  openrouter: false,
  fourthwall_base_url: "https://api.fourthwall.com",
  fourthwall_username: "",
  openrouter_base_url: "https://openrouter.ai/api/v1",
};

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
        json: () => Promise.resolve({ ...STATUS, fourthwall: true, openrouter: false }),
      }),
    );
    render(<IntegrationsStatus />);
    await waitFor(() => {
      expect(screen.getByText("Fourthwall Open API")).toBeTruthy();
      expect(screen.getByText("OpenRouter API Key")).toBeTruthy();
    });
    expect(screen.getByText("Configured")).toBeTruthy();
    expect(screen.getByText("Not configured")).toBeTruthy();
  });

  it("hides the credential form for non-admins", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(STATUS) }),
    );
    render(<IntegrationsStatus role="viewer" />);
    await waitFor(() => expect(screen.getByText("Fourthwall Open API")).toBeTruthy());
    expect(screen.queryByText("Set credentials")).toBeNull();
  });

  it("lets admins set Fourthwall and OpenRouter credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(STATUS),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<IntegrationsStatus role="admin" />);
    await waitFor(() => expect(screen.getByText("Set credentials")).toBeTruthy());

    fireEvent.change(screen.getByLabelText(/Fourthwall API username/i), {
      target: { value: "fw_api_test@fourthwall.com" },
    });
    fireEvent.change(screen.getByLabelText(/Fourthwall API password/i), {
      target: { value: "fw-password" },
    });
    fireEvent.change(screen.getByLabelText(/OpenRouter API key/i), {
      target: { value: "openrouter-test-key" },
    });
    fireEvent.click(screen.getByText("Save credentials"));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === "PATCH",
      );
      expect(patchCall).toBeTruthy();
      const body = (patchCall![1] as RequestInit).body as string;
      expect(body).toContain("openrouter-test-key");
      expect(body).toContain("fw-password");
      expect(body).toContain("fw_api_test@fourthwall.com");
    });
  });

  it("never sends blank secrets (leave-unchanged)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ...STATUS, fourthwall_username: "existing-user" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<IntegrationsStatus role="admin" />);
    await waitFor(() => expect(screen.getByText("Set credentials")).toBeTruthy());

    fireEvent.click(screen.getByText("Save credentials"));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === "PATCH",
      );
      expect(patchCall).toBeTruthy();
      const body = (patchCall![1] as RequestInit).body as string;
      // Blank password/key inputs are omitted entirely — never sent as "".
      expect(body).not.toContain("fourthwall_api_password");
      expect(body).not.toContain("openrouter_api_key");
      // The non-secret identity/endpoints are re-affirmed.
      expect(body).toContain("existing-user");
    });
  });

  it("surfaces a degraded Fourthwall test result", async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ok: false, error: "GET products failed: HTTP 401" }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(STATUS) });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<IntegrationsStatus role="admin" />);
    await waitFor(() => expect(screen.getByText("Set credentials")).toBeTruthy());

    fireEvent.click(screen.getByText("Test Fourthwall"));
    await waitFor(() => {
      expect(screen.getByText(/Fourthwall reads degraded/)).toBeTruthy();
    });
  });
});
