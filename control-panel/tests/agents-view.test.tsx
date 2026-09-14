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
