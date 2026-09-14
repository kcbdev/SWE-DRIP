import { describe, expect, it } from "vitest";

import { formatRevenue, kpiBadgeColor } from "@/lib/analytics";

describe("formatRevenue", () => {
  it("formats whole dollars", () => {
    expect(formatRevenue(32)).toBe("$32.00");
  });

  it("formats zero", () => {
    expect(formatRevenue(0)).toBe("$0.00");
  });

  it("formats decimals", () => {
    expect(formatRevenue(12.3)).toBe("$12.30");
  });
});

describe("kpiBadgeColor", () => {
  it("returns primary for passing", () => {
    expect(kpiBadgeColor(true)).toBe("text-primary");
  });

  it("returns destructive for failing", () => {
    expect(kpiBadgeColor(false)).toBe("text-destructive");
  });
});
