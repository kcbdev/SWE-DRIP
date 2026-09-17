// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import {
  devBypassEmail,
  isProductionEnv,
  shouldRedirectToLogin,
} from "../lib/auth-bypass";
import { mergeDevSession } from "../lib/auth-client";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("devBypassEmail", () => {
  it.each([undefined, "", "   ", "false", "FALSE", "False", " fAlSe "])(
    "off value %p resolves to null",
    (raw) => {
      expect(devBypassEmail(raw)).toBeNull();
    },
  );

  it.each(["dev@local", "khalid@kcb.ma", "a@b.c", "dev@localhost"])(
    "email %p enables",
    (email) => {
      expect(devBypassEmail(email)).toBe(email);
      expect(devBypassEmail(`  ${email}  `)).toBe(email);
    },
  );

  it.each(["true", "1", "yes", "not-an-email", "a@b c", "@x", "a@", "a@@b.c"])(
    "garbage %p throws loudly",
    (raw) => {
      expect(() => devBypassEmail(raw)).toThrow(/must be empty/);
    },
  );
});

describe("isProductionEnv", () => {
  it("matches production case-insensitively", () => {
    expect(isProductionEnv("production")).toBe(true);
    expect(isProductionEnv(" Production ")).toBe(true);
    expect(isProductionEnv("")).toBe(false);
    expect(isProductionEnv(undefined)).toBe(false);
    expect(isProductionEnv("development")).toBe(false);
  });
});

describe("shouldRedirectToLogin", () => {
  it("public pages and sessions never redirect", () => {
    expect(shouldRedirectToLogin("/login", false, true, null)).toBe(false);
    expect(shouldRedirectToLogin("/runs", true, false, null)).toBe(false);
  });

  it("bypass suppresses the redirect without a session", () => {
    expect(shouldRedirectToLogin("/runs", false, false, "dev@local")).toBe(false);
  });

  it("no session and no bypass redirects", () => {
    expect(shouldRedirectToLogin("/runs", false, false, null)).toBe(true);
  });
});

describe("mergeDevSession", () => {
  it("passes the real result through untouched when off", () => {
    const real = { data: null, isPending: true };
    expect(mergeDevSession(real, null)).toBe(real);
  });

  it("synthesizes an admin user over any real result", () => {
    const merged = mergeDevSession(
      { data: null, isPending: true },
      { email: "dev@local", role: "admin" },
    );
    expect(merged.isPending).toBe(false);
    expect((merged.data as { user: { email: string; role: string } }).user).toEqual({
      email: "dev@local",
      role: "admin",
    });
  });
});

describe("useSession wrapper", () => {
  it("surfaces the bypass identity once the probe succeeds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ email: "dev@local", role: "admin", devBypass: true }),
      })),
    );
    // Fresh module state per test so the probe effect re-runs.
    vi.resetModules();
    const { authClient } = await import("../lib/auth-client");

    function Probe() {
      const { data } = authClient.useSession() as {
        data: { user?: { email?: string; role?: string } } | null;
      };
      return <span>{data?.user?.role ?? "none"}:{data?.user?.email ?? "none"}</span>;
    }

    render(<Probe />);
    await waitFor(() => expect(screen.getByText("admin:dev@local")).toBeTruthy());
  });

  it("falls back to the real session when the probe 401s", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, json: async () => ({}) })),
    );
    vi.resetModules();
    const { authClient } = await import("../lib/auth-client");

    function Probe() {
      const { data } = authClient.useSession() as {
        data: { user?: { email?: string; role?: string } } | null;
      };
      return <span>{data?.user?.role ?? "none"}</span>;
    }

    render(<Probe />);
    // Real better-auth hook without credentials resolves to no session;
    // the wrapper must pass that through instead of crashing.
    await waitFor(() => expect(screen.getByText("none")).toBeTruthy());
  });
});
