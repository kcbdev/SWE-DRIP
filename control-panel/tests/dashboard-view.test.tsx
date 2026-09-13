// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { DashboardView } from "../components/dashboard/dashboard-view";
import type { DashboardSummary } from "../lib/dashboard";

afterEach(cleanup);

function summary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    pending_approvals: { count: 0, items: [] },
    spend: { spend_usd: 0, cap_usd: 130, pct: 0, warning: false, call_count: 0 },
    collections: { count: 0, at_risk: false, items: [] },
    activity: [],
    sources: { spend: "ok", collections: "ok", activity: "ok", pending_approvals: "ok" },
    ...overrides,
  };
}

describe("DashboardView", () => {
  it("renders honest empty states", () => {
    render(<DashboardView summary={summary()} />);
    expect(screen.getByText("No pending approvals.")).toBeTruthy();
    expect(screen.getByText("No recent activity.")).toBeTruthy();
    expect(screen.getByText("$0.00 (0%)")).toBeTruthy();
    expect(screen.getAllByText("0").length).toBeGreaterThanOrEqual(2);
  });

  it("renders populated cards and feed", () => {
    render(
      <DashboardView
        summary={summary({
          pending_approvals: { count: 3, items: [{ id: "a-1", type: "collection_contract", collection: "gym" }] },
          spend: { spend_usd: 50, cap_usd: 130, pct: 0.3846, warning: false, call_count: 12 },
          collections: { count: 2, at_risk: false, items: [] },
          activity: [
            { action: "publish", entity_type: "product", entity_id: "p-1", actor: "u-1", created_at: new Date().toISOString() },
          ],
        })}
      />
    );
    expect(screen.getByText("3")).toBeTruthy();
    expect(screen.getByText("$50.00 (38%)")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText("publish")).toBeTruthy();
  });

  it("flags spend above 80% with the warning style", () => {
    const { container } = render(
      <DashboardView
        summary={summary({
          spend: { spend_usd: 104.01, cap_usd: 130, pct: 0.8001, warning: true, call_count: 40 },
        })}
      />
    );
    const warning = container.querySelector('[data-warning="true"]');
    expect(warning).toBeTruthy();
    expect(warning?.className).toContain("text-warning");
  });

  it("flags at-risk collections", () => {
    const { container } = render(
      <DashboardView summary={summary({ collections: { count: 1, at_risk: true, items: [] } })} />
    );
    expect(container.querySelector('[data-at-risk="true"]')).toBeTruthy();
  });

  it("shows explicit unavailable states for broken sources", () => {
    render(<DashboardView summary={summary({ spend: null, collections: null, activity: null, pending_approvals: { count: null, items: [] } })} />);
    expect(screen.getAllByText("source unavailable").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  it("shows the error when no summary is available", () => {
    render(<DashboardView summary={null} error="API 500" />);
    expect(screen.getByText("API 500")).toBeTruthy();
  });
});
