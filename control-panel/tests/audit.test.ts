import { describe, expect, it } from "vitest";

import { authEventForPath } from "../lib/audit";

describe("auth event mapping", () => {
  it("maps sign-in and sign-out to audit actions", () => {
    expect(authEventForPath("/sign-in/email")).toEqual({
      action: "auth.login",
      entityType: "session",
    });
    expect(authEventForPath("/sign-out")).toEqual({
      action: "auth.logout",
      entityType: "session",
    });
  });

  it("ignores non-state-changing auth paths", () => {
    expect(authEventForPath("/get-session")).toBeNull();
    expect(authEventForPath("/")).toBeNull();
  });
});
