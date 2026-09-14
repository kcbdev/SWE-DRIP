// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CollectionKpiCard, KpiSeriesTable, OverviewChart, RetirementBanner } from "@/components/analytics/analytics-view";
import type { CollectionKpiResponse, OverviewResponse, RetirementRecommendation } from "@/lib/analytics";

afterEach(() => { cleanup(); });

const overview: OverviewResponse = {
  revenue_12m: 1234.56,
  units_12m: 37,
  break_even: 600.0,
  above_break_even: true,
  active_product_types: 3,
};

const kpi: CollectionKpiResponse = {
  collection_id: "vibe-coding",
  kpi: {
    series: [
      { window_days: 7, units: 5, revenue: 160.0, passes_min_units: true, passes_min_conversion: true },
      { window_days: 30, units: 20, revenue: 640.0, passes_min_units: true, passes_min_conversion: true },
    ],
    thresholds: { min_units: 3, min_conversion: null, eval_window_days: 7 },
  },
  summary: { units_in_eval_window: 5, revenue_in_eval_window: 160.0, below_min_units: false, below_min_conversion: false },
};

describe("OverviewChart", () => {
  it("renders revenue and break-even", () => {
    render(<OverviewChart overview={overview} />);
    expect(screen.getByText("$1234.56")).toBeDefined();
    expect(screen.getByText("37")).toBeDefined();
    expect(screen.getByText("$600.00 ✓")).toBeDefined();
  });
});

describe("CollectionKpiCard", () => {
  it("renders collection id and units", () => {
    render(<ul><CollectionKpiCard kpi={kpi} /></ul>);
    expect(screen.getByText("vibe-coding")).toBeDefined();
    expect(screen.getByText(/units in eval window/)).toBeDefined();
  });

  it("shows below-threshold status", () => {
    const below = { ...kpi, summary: { ...kpi.summary, below_min_units: true } };
    render(<ul><CollectionKpiCard kpi={below} /></ul>);
    expect(screen.getByText("below threshold")).toBeDefined();
  });
});

describe("KpiSeriesTable", () => {
  it("renders window rows", () => {
    render(<KpiSeriesTable kpi={kpi} />);
    expect(screen.getByText("7 days")).toBeDefined();
    expect(screen.getByText("30 days")).toBeDefined();
    const table = screen.getByRole("table");
    expect(within(table).getAllByText("5")).toHaveLength(1);
    expect(within(table).getAllByText("20")).toHaveLength(1);
  });
});

describe("RetirementBanner", () => {
  it("renders when recommended", () => {
    const rec = { verdict: "retirement_recommended" as const, reason: "low units", collection_id: "vibe-coding" } as RetirementRecommendation;
    const { container } = render(<RetirementBanner rec={rec} />);
    const banner = container.querySelector("div")!;
    expect(within(banner).getByText((_, el) => el?.tagName === "P" && el?.textContent?.includes("Retirement recommended for vibe-coding"))).toBeDefined();
  });

  it("renders nothing when not recommended", () => {
    const rec = { verdict: "no_recommendation" as const, reason: "met", collection_id: "vibe-coding" } as RetirementRecommendation;
    const { container } = render(<RetirementBanner rec={rec} />);
    expect(container.innerHTML).toBe("");
  });
});
