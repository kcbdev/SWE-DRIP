#!/usr/bin/env node
"use strict";

/**
 * Docs-contract lint — SWE Drip v1.
 *
 * Verifies that the v1 spec kit still carries its locked invariants and that
 * the constitution (AGENTS.md) declares the verified Plane binding and a
 * Context Map. Zero dependencies, offline, deterministic.
 *
 * Rule: every app-stack PBI must extend these gates (Next.js build/test,
 * pytest, schema checks) — never weaken them. See AGENTS.md section 2.
 */

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
let checks = 0;
const failures = [];

function check(cond, msg) {
  checks += 1;
  if (!cond) failures.push(msg);
}

function readText(rel) {
  const abs = path.join(ROOT, rel);
  if (!fs.existsSync(abs)) {
    failures.push(`missing file: ${rel}`);
    return null;
  }
  return fs.readFileSync(abs, "utf8");
}

function expectIncludes(rel, text, needles) {
  if (text === null) return;
  for (const needle of needles) {
    check(text.includes(needle), `${rel}: missing "${needle}"`);
  }
}

// ---------------------------------------------------------------- spec kit
const DOCS = {
  vision: "docs/swe-drip-product-vision-v1.md",
  definition: "docs/swe-drip-product-definition-v1.md",
  prd: "docs/swe-drip-prd-v1.md",
  ux: "docs/swe-drip-ux-spec-v1.md",
  tech: "docs/swe-drip-technical-spec-v1.md",
  data: "docs/swe-drip-data-api-llm-spec-v1.md",
  delivery: "docs/swe-drip-delivery-acceptance-spec-v1.md",
};

const texts = {};
for (const [key, rel] of Object.entries(DOCS)) {
  texts[key] = readText(rel);
}

for (const rel of [
  "docs/design ref/swe_drip_control_panel_dashboard.html",
  "docs/design ref/swe_drip_control_panel_approvals.html",
  "docs/design ref/swe_drip_control_panel_design_qc.html",
]) {
  check(fs.existsSync(path.join(ROOT, rel)), `missing design ref: ${rel}`);
}

// ---------------------------------------------------------- locked contracts
expectIncludes(DOCS.vision, texts.vision, [
  "Trend research + clustering",
  "Collection contract approval",
  "Listing copy",
  "Design spec",
  "Art render",
  "Placement & colorway resolution",
  "Aesthetic QC",
  "Technical QC",
  "Fourthwall product create",
  "Publish gate",
  "Shelf (pricing/collection assignment)",
  "LangGraph",
  "interrupt()",
  "Postgres checkpointer",
  "$130",
]);

expectIncludes(DOCS.definition, texts.definition, [
  "$32",
  "$62",
  "$20",
  "#0D0D0D",
  "#00FF41",
  "JetBrains Mono",
]);

expectIncludes(DOCS.prd, texts.prd, [
  "Admin",
  "Operator",
  "Viewer",
  "FR-24",
  "NFR-4",
]);

expectIncludes(DOCS.ux, texts.ux, ["shadcn/ui", "#0D0D0D", "#00FF41"]);

expectIncludes(DOCS.tech, texts.tech, [
  "Next.js 15",
  "FastAPI",
  "Postgres",
  "Fourthwall MCP",
  "audit log",
]);

expectIncludes(DOCS.data, texts.data, [
  "collection_id",
  "kpi_thresholds",
  "audit_log",
  "pipeline_runs",
  "hitl_approvals",
  "OpenRouter",
  "google/gemini-2.0-flash-001",
  "anthropic/claude-sonnet-4-6",
  "riverflow-v2-pro",
]);

if (texts.delivery !== null) {
  for (let i = 1; i <= 19; i += 1) {
    check(
      texts.delivery.includes(`- A${i}:`),
      `${DOCS.delivery}: missing acceptance criterion A${i}`
    );
  }
  expectIncludes(DOCS.delivery, texts.delivery, ["CC-1", "CC-2", "CC-3", "Phase 7"]);
}

// ------------------------------------------------------------- constitution
const agents = readText("AGENTS.md");
if (agents !== null) {
  check(/^Plane workspace: kcb$/m.test(agents), "AGENTS.md: missing 'Plane workspace: kcb'");
  const projectLine = agents.match(/^Plane project: (.+)$/m);
  check(projectLine !== null, "AGENTS.md: missing 'Plane project:' line");
  if (projectLine) {
    check(
      projectLine[1].includes("d162b6d4-1205-4eea-9ef3-871354c5e8a3"),
      "AGENTS.md: Plane project id does not match the verified SWDRP project"
    );
    check(
      projectLine[1].includes("SWDRP"),
      "AGENTS.md: Plane project line should carry the SWDRP identifier"
    );
  }
  expectIncludes("AGENTS.md", agents, [
    "## 2. Commands",
    "## 5. Context Map",
    "project_structure:",
    "documentation_index:",
    "cmd /c \"npm run verify\"",
  ]);
}

// --------------------------------------------------------------- gate chain
const pkgText = readText("package.json");
if (pkgText !== null) {
  try {
    const pkg = JSON.parse(pkgText);
    const scripts = pkg.scripts || {};
    for (const name of ["build", "lint", "test", "verify"]) {
      check(typeof scripts[name] === "string", `package.json: missing script "${name}"`);
    }
    check(
      typeof scripts.verify === "string" && scripts.verify.includes("npm run lint"),
      "package.json: verify must chain the lint gate"
    );
  } catch (err) {
    failures.push(`package.json: invalid JSON (${err.message})`);
  }
}

// ------------------------------------------------------------- secret scan
const SECRET_PATTERNS = [
  /sk-or-[A-Za-z0-9]/,
  /gho_[A-Za-z0-9]/,
  /github_pat_/,
  /AKIA[0-9A-Z]{16}/,
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
];
const SKIP_DIRS = new Set([".git", "node_modules"]);

const SELF = path.join("scripts", "lint.js");

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const abs = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(abs);
    } else if (entry.isFile() && path.relative(ROOT, abs) !== SELF) {
      let content;
      try {
        content = fs.readFileSync(abs, "utf8");
      } catch {
        continue;
      }
      for (const pattern of SECRET_PATTERNS) {
        check(!pattern.test(content), `possible secret in ${path.relative(ROOT, abs)} (${pattern})`);
      }
    }
  }
}
walk(ROOT);

// ---------------------------------------------------------------------- out
if (failures.length > 0) {
  console.error(`lint: ${failures.length} contract failure(s):`);
  for (const f of failures) console.error(`  - ${f}`);
  process.exit(1);
}
console.log(`lint: all contracts OK (${checks} checks)`);
