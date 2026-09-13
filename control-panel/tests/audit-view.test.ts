import { describe, expect, it } from "vitest";

import { buildAuditQuery, formatDiff } from "../lib/audit-view";

describe("buildAuditQuery", () => {
  it("returns an empty string with no filters", () => {
    expect(buildAuditQuery({})).toBe("");
  });

  it("includes every populated filter", () => {
    const query = buildAuditQuery({
      actor: "u-1",
      action: "role.change",
      entity_type: "user",
      entity_id: "u-2",
      start: "2026-01-01",
      end: "2026-12-31",
      limit: 100,
    });
    expect(query).toContain("actor=u-1");
    expect(query).toContain("action=role.change");
    expect(query).toContain("entity_type=user");
    expect(query).toContain("entity_id=u-2");
    expect(query).toContain("start=2026-01-01");
    expect(query).toContain("end=2026-12-31");
    expect(query).toContain("limit=100");
  });
});

describe("formatDiff", () => {
  it("renders before → after", () => {
    expect(formatDiff({ role: "viewer" }, { role: "operator" })).toBe(
      '{"role":"viewer"} → {"role":"operator"}'
    );
  });

  it("uses an em dash for missing sides", () => {
    expect(formatDiff(null, { role: "operator" })).toBe('— → {"role":"operator"}');
  });
});
