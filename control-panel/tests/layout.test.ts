import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const appDir = join(root, "app");

/** Recursively collect every route file under app/. */
function collect(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) collect(full, out);
    else if (entry === "page.tsx") out.push(full);
  }
  return out;
}

const pages = collect(appDir);
const rel = (file: string) => relative(root, file).split(sep).join("/");

describe("app layout consistency", () => {
  it("finds every page", () => {
    expect(pages.length).toBeGreaterThan(15);
  });

  it("every page except login renders the shared AppShell (sidebar)", () => {
    const offenders = pages
      .filter((file) => !rel(file).includes("(auth)"))
      .filter((file) => !readFileSync(file, "utf8").includes("AppShell"))
      .map(rel);
    expect(offenders).toEqual([]);
  });

  it("the login page does not render the shell", () => {
    const login = pages.find((file) => rel(file).includes("(auth)/login"));
    expect(login).toBeTruthy();
    expect(readFileSync(login!, "utf8")).not.toContain("AppShell");
  });
});
