import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel: string) => readFileSync(join(root, rel), "utf8");

describe("auth UI", () => {
  it("login page signs in with Better Auth email/password", () => {
    const page = read("app/(auth)/login/page.tsx");
    expect(page).toContain("authClient.signIn.email");
    expect(page).toContain("Invite-only");
  });

  it("login page redirects signed-in users away and refreshes session after sign-in", () => {
    const page = read("app/(auth)/login/page.tsx");
    expect(page).toContain('router.replace("/")');
    expect(page).toContain("router.refresh()");
    expect(page).toContain("useSession");
  });

  it("middleware gates every page on session-cookie presence", () => {
    const middleware = read("middleware.ts");
    expect(middleware).toContain("__Secure-better-auth.session_token");
    expect(middleware).toContain("better-auth.session_token");
    expect(middleware).toContain('new URL("/login"');
  });

  it("shell gates the admin nav and offers logout", () => {
    const shell = read("components/app-shell.tsx");
    expect(shell).toContain("isAdmin");
    expect(shell).toContain("authClient.signOut");
    expect(shell).toContain("/settings/users");
  });

  it("users screen calls the admin API and hides for non-admins", () => {
    const page = read("app/settings/users/page.tsx");
    expect(page).toContain("/api/users");
    expect(page).toContain("Admin role required");
    expect(page).toContain("deactivate");
  });
});
