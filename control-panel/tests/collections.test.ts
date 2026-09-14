import { describe, expect, it } from "vitest";

import {
  creationErrors,
  filterCollections,
  lifecycleDaysLeft,
  parseSurvivors,
  type CollectionRecord,
} from "../lib/collections";

function record(id: string, status: "draft" | "active" | "retired"): CollectionRecord {
  return {
    id,
    mtime: 0,
    contract: {
      collection_id: id,
      theme: id,
      status,
      style_archetype: "s",
      illustration_rules: { line_weight: null, palette: [], no_mixed_styles: true },
      garment_colorways: [],
      placement_templates: [],
      product_count_target: null,
      lifecycle_days: 90,
      kpi_thresholds: { min_units: null, min_conversion: null, eval_window_days: null },
      created_by: "u",
      created_at: "2026-09-14T10:00:00.000Z",
      approved_at: "2026-09-14T10:00:00.000Z",
      retired_at: null,
    },
  };
}

describe("collections helpers", () => {
  it("filters by status incl candidates label mapping", () => {
    const items = [record("a", "active"), record("d", "draft"), record("r", "retired")];
    expect(filterCollections(items, "all")).toHaveLength(3);
    expect(filterCollections(items, "draft").map((i) => i.id)).toEqual(["d"]);
    expect(filterCollections(items, "active").map((i) => i.id)).toEqual(["a"]);
  });

  it("computes lifecycle countdown", () => {
    const now = new Date("2026-09-19T10:00:00.000Z").getTime();
    expect(lifecycleDaysLeft(record("a", "active").contract, now)).toBe(85);
    expect(lifecycleDaysLeft(record("d", "draft").contract, now)).toBeNull();
  });

  it("validates creation input client-side", () => {
    expect(creationErrors({ collection_id: "Bad Slug!", theme: "" })).toHaveLength(2);
    expect(creationErrors({ collection_id: "vibe-coding", theme: "Vibe" })).toEqual([]);
  });

  it("parses survivor lists", () => {
    expect(parseSurvivors("fw-1, fw-2 ,,")).toEqual(["fw-1", "fw-2"]);
  });
});
