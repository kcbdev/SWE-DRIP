// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { CatalogGrid } from "../components/catalog/catalog-grid";
import type { CatalogItem } from "../lib/catalog";

afterEach(cleanup);

const ITEMS: CatalogItem[] = [
  { id: "fw-tee", title: "Vibe Tee", status: "DRAFT", category: "tee", price: 32, invariant: { status: "pass", expected: 32, actual: 32, reason: null }, survivor_of: "vibe-coding" },
  { id: "fw-hoodie", title: "Vibe Hoodie", status: "DRAFT", category: "hoodie", price: 70, invariant: { status: "fail", expected: 62, actual: 70, reason: "hoodie must be $62" }, survivor_of: null },
];

describe("CatalogGrid", () => {
  it("renders the product grid with invariant badges", () => {
    render(<CatalogGrid items={ITEMS} />);
    expect(screen.getByText("Vibe Tee")).toBeTruthy();
    expect(screen.getByText("invariant pass")).toBeTruthy();
    expect(screen.getByText("invariant fail (expected $62)")).toBeTruthy();
  });

  it("flags survivors", () => {
    render(<CatalogGrid items={ITEMS} />);
    expect(screen.getByText(/survivor of vibe-coding/)).toBeTruthy();
  });

  it("shows an empty state", () => {
    render(<CatalogGrid items={[]} />);
    expect(screen.getByText("No products in the mirror.")).toBeTruthy();
  });
});
