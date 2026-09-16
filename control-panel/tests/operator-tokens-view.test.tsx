// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { OperatorTokens } from "../components/settings/operator-tokens";
import { fetchTokens, issueToken, mcpEndpointUrl, revokeToken } from "../lib/operator-tokens";

afterEach(cleanup);

const TOKEN_VALUE = "sdr_test-issued-value";

function row(revoked = false) {
  return {
    id: 1, prefix: "sdr_test", name: "ci", scopes: ["read"], created_by: "u-9",
    revoked, last_used_at: null, created_at: "2026-09-16T00:00:00+00:00",
  };
}

function mockApi(state: { revoked: boolean }) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST" && url.endsWith("/api/operator-tokens")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ...row(), token: TOKEN_VALUE }),
        });
      }
      if (init?.method === "POST" && url.includes("/revoke")) {
        state.revoked = true;
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ id: 1, prefix: "sdr_test", revoked: true }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [row(state.revoked)] }),
      });
    }),
  );
}

describe("operator-tokens lib", () => {
  it("fetches the token list", async () => {
    mockApi({ revoked: false });
    const items = await fetchTokens();
    expect(items[0].prefix).toBe("sdr_test");
    expect(fetch).toHaveBeenCalledWith("/api/operator-tokens", expect.anything());
  });

  it("issues with name and scopes", async () => {
    mockApi({ revoked: false });
    const issued = await issueToken("ci", ["operate"]);
    expect(issued.token).toBe(TOKEN_VALUE);
    expect(fetch).toHaveBeenCalledWith(
      "/api/operator-tokens",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"operate"'),
      }),
    );
  });

  it("revokes by id", async () => {
    mockApi({ revoked: false });
    const result = await revokeToken(1);
    expect(result.revoked).toBe(true);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/operator-tokens/1/revoke"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("derives the MCP endpoint from the API base", () => {
    expect(mcpEndpointUrl()).toContain("/mcp/");
  });

  it("honours NEXT_PUBLIC_API_BASE_URL with public fallback", () => {
    const saved = process.env.NEXT_PUBLIC_API_BASE_URL;
    try {
      process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.test";
      expect(mcpEndpointUrl()).toBe("https://api.example.test/mcp/");
      delete process.env.NEXT_PUBLIC_API_BASE_URL;
      expect(mcpEndpointUrl()).toBe("https://swedrip-api.kcb.ma/mcp/");
    } finally {
      if (saved === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
      else process.env.NEXT_PUBLIC_API_BASE_URL = saved;
    }
  });
});

describe("OperatorTokens section", () => {
  it("admin sees metadata but never values", async () => {
    mockApi({ revoked: false });
    render(<OperatorTokens role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("ci")).toBeTruthy();
    });
    expect(screen.getByText(/sdr_test/)).toBeTruthy();
    expect(screen.queryByText(TOKEN_VALUE)).toBeNull();
    expect("token" in (await fetchTokens())[0]).toBe(false);
  });

  it("issue shows the value once, dismiss clears it for good", async () => {
    mockApi({ revoked: false });
    render(<OperatorTokens role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("ci")).toBeTruthy();
    });
    fireEvent.change(screen.getByPlaceholderText("e.g. opencode-runner"), {
      target: { value: "ci-2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Issue token" }));
    await waitFor(() => {
      expect(screen.getByTestId("issued-token")).toBeTruthy();
    });
    expect(screen.getByText(TOKEN_VALUE)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    expect(screen.queryByTestId("issued-token")).toBeNull();
    expect(screen.queryByText(TOKEN_VALUE)).toBeNull();
  });

  it("copy uses the clipboard and confirms", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window.navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    mockApi({ revoked: false });
    render(<OperatorTokens role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("ci")).toBeTruthy();
    });
    fireEvent.change(screen.getByPlaceholderText("e.g. opencode-runner"), {
      target: { value: "ci-2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Issue token" }));
    await waitFor(() => {
      expect(screen.getByTestId("issued-token")).toBeTruthy();
    });
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(TOKEN_VALUE);
      expect(screen.getByText("Copied")).toBeTruthy();
    });
  });

  it("revoke requires confirm then flags the row", async () => {
    const state = { revoked: false };
    mockApi(state);
    render(<OperatorTokens role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("ci")).toBeTruthy();
    });
    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    expect(screen.getByRole("button", { name: "Confirm revoke" })).toBeTruthy();
    // Not revoked yet — no premature call.
    expect(fetch).not.toHaveBeenCalledWith(
      expect.stringContaining("/revoke"),
      expect.anything(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm revoke" }));
    await waitFor(() => {
      expect(screen.getByText("revoked")).toBeTruthy();
    });
  });

  it.each([["viewer"], ["operator"], [undefined]])(
    "non-admin (%s) renders no section and fetches nothing",
    async (role) => {
      mockApi({ revoked: false });
      const { container } = render(<OperatorTokens role={role as string | undefined} />);
      expect(container.textContent).toBe("");
      expect(fetch).not.toHaveBeenCalled();
    },
  );

  it("shows the client config snippet", async () => {
    mockApi({ revoked: false });
    render(<OperatorTokens role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("ci")).toBeTruthy();
    });
    const section = screen.getByTestId("operator-tokens");
    expect(within(section).getByText(/streamable-http/)).toBeTruthy();
  });

  it("copies the client config snippet", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window.navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    mockApi({ revoked: false });
    render(<OperatorTokens role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("ci")).toBeTruthy();
    });
    fireEvent.click(screen.getByRole("button", { name: "Copy client config" }));
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining("streamable-http"));
      expect(screen.getByText("Copied")).toBeTruthy();
    });
  });

  it("empty name blocks issuance without a request", async () => {
    mockApi({ revoked: false });
    render(<OperatorTokens role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("ci")).toBeTruthy();
    });
    (fetch as unknown as ReturnType<typeof vi.fn>).mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Issue token" }));
    expect(await screen.findByText("Token name is required")).toBeTruthy();
    expect(fetch).not.toHaveBeenCalledWith(
      expect.stringContaining("/api/operator-tokens"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("server rejection surfaces as an error", async () => {
    mockApi({ revoked: false });
    render(<OperatorTokens role="admin" />);
    await waitFor(() => {
      expect(screen.getByText("ci")).toBeTruthy();
    });
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementationOnce(() =>
      Promise.resolve({ ok: false, status: 409, json: () => Promise.resolve({}) }),
    );
    fireEvent.change(screen.getByPlaceholderText("e.g. opencode-runner"), {
      target: { value: "dup" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Issue token" }));
    await waitFor(() => {
      expect(screen.getByText(/API 409/)).toBeTruthy();
    });
  });
});
