import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel: string) => readFileSync(join(root, rel), "utf8");

describe("brand shell tokens", () => {
  const rawCss = read("app/globals.css");
  const css = rawCss.toLowerCase();

  it("uses void black as the background", () => {
    expect(css).toContain("#0d0d0d");
  });

  it("uses terminal green as the accent", () => {
    expect(css).toContain("#00ff41");
  });

  it("declares JetBrains Mono for data/mono content", () => {
    expect(rawCss).toContain("JetBrains Mono");
  });

  it("flattens radii so no rounded pills can render", () => {
    expect(css).toContain("--radius: 0rem");
    expect(css).toContain("--radius-sm: 0rem");
  });

  it("wires the brand tokens into the shell", () => {
    const layout = read("app/layout.tsx");
    const page = read("app/page.tsx");
    expect(layout).toContain("bg-background");
    expect(layout).toContain("text-foreground");
    expect(page).toContain("font-mono");
    expect(page).toContain("text-primary");
  });
});
