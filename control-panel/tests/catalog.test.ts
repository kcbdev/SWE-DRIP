import { describe, expect, it } from "vitest";

import { badgeLabel } from "../lib/catalog";

describe("catalog helpers", () => {
  it("labels pass/fail badges", () => {
    expect(
      badgeLabel({ id: "a", title: "T", status: null, category: "tee", price: 32, invariant: { status: "pass", expected: 32, actual: 32, reason: null }, survivor_of: null }),
    ).toBe("invariant pass");
    expect(
      badgeLabel({ id: "b", title: "H", status: null, category: "hoodie", price: 70, invariant: { status: "fail", expected: 62, actual: 70, reason: "x" }, survivor_of: null }),
    ).toBe("invariant fail (expected $62)");
  });

  it("surfaces unmapped reasons verbatim", () => {
    expect(
      badgeLabel({ id: "c", title: "M", status: null, category: null, price: 10, invariant: { status: "unmapped", expected: null, actual: 10, reason: "category unmapped — no invariant rule applies" }, survivor_of: null }),
    ).toContain("unmapped");
  });
});
