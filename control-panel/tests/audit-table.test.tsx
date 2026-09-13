// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { AuditTable } from "../components/audit/audit-table";
import type { AuditEntry } from "../lib/audit-view";

afterEach(cleanup);

const ENTRIES: AuditEntry[] = [
  {
    id: 1,
    actor_user_id: "u-1",
    created_at: "2026-09-13T10:00:00Z",
    action: "role.change",
    entity_type: "user",
    entity_id: "u-2",
    before_json: { role: "viewer" },
    after_json: { role: "operator" },
  },
];

function renderTable(overrides: Partial<Parameters<typeof AuditTable>[0]> = {}) {
  return render(
    <AuditTable entries={ENTRIES} filters={{}} onChange={() => {}} exportBase="/api/audit?" {...overrides} />
  );
}

describe("AuditTable", () => {
  it("renders the before → after diff", () => {
    renderTable();
    expect(screen.getByText(/\{"role":"viewer"\} → \{"role":"operator"\}/)).toBeTruthy();
  });

  it("emits filter changes", () => {
    const onChange = vi.fn();
    renderTable({ onChange });
    fireEvent.change(screen.getByLabelText("Actor"), { target: { value: "u-9" } });
    expect(onChange).toHaveBeenCalledWith("actor", "u-9");
  });

  it("exposes CSV and JSON export downloads", () => {
    renderTable();
    const csv = screen.getByText("Export CSV").closest("a");
    const json = screen.getByText("Export JSON").closest("a");
    expect(csv?.getAttribute("href")).toContain("format=csv");
    expect(csv?.getAttribute("download")).toBe("audit-log.csv");
    expect(json?.getAttribute("href")).toContain("format=json");
  });

  it("shows an empty state when no rows match", () => {
    renderTable({ entries: [] });
    expect(screen.getByText("No audit rows match the filters.")).toBeTruthy();
  });
});
