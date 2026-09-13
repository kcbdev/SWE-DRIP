"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}

function exists(rel) {
  return fs.existsSync(path.join(ROOT, rel));
}

const VISION = "docs/swe-drip-product-vision-v1.md";
const DEFINITION = "docs/swe-drip-product-definition-v1.md";
const PRD = "docs/swe-drip-prd-v1.md";
const UX = "docs/swe-drip-ux-spec-v1.md";
const TECH = "docs/swe-drip-technical-spec-v1.md";
const DATA = "docs/swe-drip-data-api-llm-spec-v1.md";
const DELIVERY = "docs/swe-drip-delivery-acceptance-spec-v1.md";

test("spec kit: the seven v1 documents exist and carry content", () => {
  const docs = [VISION, DEFINITION, PRD, UX, TECH, DATA, DELIVERY];
  for (const rel of docs) {
    assert.ok(exists(rel), `${rel} must exist`);
    assert.ok(read(rel).length > 1000, `${rel} must be non-trivial`);
  }
});

test("spec kit: control panel design references are present", () => {
  for (const rel of [
    "docs/design ref/swe_drip_control_panel_dashboard.html",
    "docs/design ref/swe_drip_control_panel_approvals.html",
    "docs/design ref/swe_drip_control_panel_design_qc.html",
  ]) {
    assert.ok(exists(rel), `${rel} must exist`);
  }
});

test("vision: pipeline carries the locked 11-node list", () => {
  const vision = read(VISION);
  const nodes = [
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
  ];
  for (const node of nodes) {
    assert.ok(vision.includes(node), `vision must list node "${node}"`);
  }
});

test("vision: HITL gates stay config-driven, not structural", () => {
  const vision = read(VISION);
  const onMarkers = vision.match(/\*\*On\*\*/g) || [];
  assert.ok(onMarkers.length >= 3, "at least three nodes default HITL On");
  assert.ok(vision.includes("interrupt()"), "HITL is implemented via interrupt()");
});

test("definition: price invariants are locked at $32 / $62 / $20", () => {
  const definition = read(DEFINITION);
  for (const price of ["$32", "$62", "$20"]) {
    assert.ok(definition.includes(price), `definition must lock ${price}`);
  }
});

test("definition + ux: brand lock colors and typeface hold", () => {
  for (const rel of [DEFINITION, UX]) {
    const text = read(rel);
    assert.ok(text.includes("#0D0D0D"), `${rel} must carry void black`);
    assert.ok(text.includes("#00FF41"), `${rel} must carry terminal green`);
  }
  assert.ok(read(DEFINITION).includes("JetBrains Mono"), "typeface lock must hold");
});

test("prd: three launch roles are defined", () => {
  const prd = read(PRD);
  for (const role of ["Admin", "Operator", "Viewer"]) {
    assert.ok(prd.includes(role), `prd must define role ${role}`);
  }
});

test("delivery: acceptance criteria A1-A19 and CC-1-CC-3 are present", () => {
  const delivery = read(DELIVERY);
  for (let i = 1; i <= 19; i += 1) {
    assert.ok(delivery.includes(`- A${i}:`), `delivery must define A${i}`);
  }
  for (let i = 1; i <= 3; i += 1) {
    assert.ok(delivery.includes(`CC-${i}`), `delivery must define CC-${i}`);
  }
});

test("tech: control panel stack is fixed", () => {
  const tech = read(TECH);
  for (const needle of ["Next.js 15", "shadcn/ui", "FastAPI", "Postgres"]) {
    assert.ok(tech.includes(needle), `tech spec must fix ${needle}`);
  }
});

test("data: per-node model routing replaces the single-model override", () => {
  const data = read(DATA);
  for (const model of [
    "google/gemini-2.0-flash-001",
    "anthropic/claude-sonnet-4-6",
    "riverflow-v2-pro",
  ]) {
    assert.ok(data.includes(model), `routing table must name ${model}`);
  }
  assert.ok(
    data.includes("per-node"),
    "routing must be declared per-node, not gateway-overridden"
  );
});

test("governance: AGENTS.md declares the verified kcb/SWDRP binding", () => {
  const agents = read("AGENTS.md");
  assert.match(agents, /^Plane workspace: kcb$/m, "workspace line required at top level");
  const project = agents.match(/^Plane project: (.+)$/m);
  assert.ok(project, "project line required at top level");
  assert.ok(
    project[1].includes("d162b6d4-1205-4eea-9ef3-871354c5e8a3"),
    "project line must carry the verified SWDRP id"
  );
  assert.ok(project[1].includes("SWDRP"), "project line must carry the SWDRP identifier");
});

test("governance: Context Map carries project_structure and documentation_index", () => {
  const agents = read("AGENTS.md");
  assert.ok(agents.includes("project_structure:"), "project_structure section required");
  assert.ok(agents.includes("documentation_index:"), "documentation_index section required");
});

test("gates: package.json wires build, lint, test, verify", () => {
  const pkg = JSON.parse(read("package.json"));
  for (const name of ["build", "lint", "test", "verify"]) {
    assert.equal(typeof pkg.scripts[name], "string", `script ${name} required`);
  }
  assert.ok(pkg.scripts.verify.includes("npm run lint"), "verify chains lint");
  assert.ok(pkg.scripts.verify.includes("npm test"), "verify chains test");
});
