Plane workspace: kcb
Plane project: d162b6d4-1205-4eea-9ef3-871354c5e8a3 # SWDRP — SWE DRIP (MCP server: plane-kcb)

# AGENTS.md — SWE Drip V1 Constitution

> This repo is bound to Plane `kcb / SWDRP (d162b6d4-1205-4eea-9ef3-871354c5e8a3)` — verified via MCP `plane-kcb` on 2026-09-13. All `asdlc-plane` sync is strictly scoped to that project. `Backlog` is ignored until moved to `Todo`.
>
> V1 is the **clean-room custom implementation**: the Paperclip/Hermes POC (`kcbdev/SWE-DRIP-POC`) is retired as a runtime for the core pipeline (Vision doc §3.1). The POC repo is a **reference only** — see §3.

## 1. Stack

| Layer | Choice | Notes |
|---|---|---|
| Docs / Specs | Markdown + YAML | `docs/` holds the v1.0 spec kit (source of truth); `specs/` will hold feature specs derived by `asdlc-plan` |
| Verification (current) | Node 22 + `node:test` | Docs-contract gates (`npm run verify`); zero dependencies |
| Verification (target) | Next.js test/build + pytest | App-stack PBIs must extend the gates, never weaken them |
| Control Panel (target) | Next.js 15 (App Router) + shadcn/ui | Dark/black theme only, brand tokens as CSS variables |
| API (target) | FastAPI (Python) | Auth/RBAC, checkpointer read/write, audit writer, Fourthwall MCP client |
| Data (target) | Postgres (pgvector-capable, existing instance) | LangGraph checkpointer + audit log + users/roles; collection contracts stay YAML |
| Orchestration (target) | LangGraph `StateGraph` + Postgres checkpointer | 11-node pipeline, `interrupt()`/`Command(resume=...)` HITL |
| Storefront | Fourthwall (external, system of record) | Never owned by this repo; reads via Fourthwall MCP (OAuth2) |
| Models | OpenRouter, **per-node** model IDs | See `docs/swe-drip-data-api-llm-spec-v1.md` §3 |
| Infra (target) | Existing Coolify/Hetzner | No new hosting provider |

No Paperclip/Hermes in this repo's runtime. No compiled service exists yet — the Node docs-contract harness is the only executable code today.

## 2. Commands (deterministic gates)

Run from repo root. All gates must pass before any PBI moves to In Review.

```bash
# Build — docs gates (no compilation) + Control Panel production build
cmd /c "npm run build"
cmd /c "npm run verify:web"   # cd control-panel && next build && vitest run

# Lint — spec-kit contracts + constitution checks + polyglot gate checks
cmd /c "npm run lint"
# or
npm run lint   # -> node scripts/lint.js

# Test — docs smoke suite (node:test) + Python suites
cmd /c "npm test"
cmd /c "npm run verify:api"   # python -m pytest api/tests pipeline/tests -q

# Full verification (Ralph Loop gate) — docs + web + api, fully offline
cmd /c "npm run verify"
# or
npm run verify # -> build && lint && test && verify:web && verify:api && verify:parity
```

Expected results (baseline 2026-09-13, post PBI-001…003):
- `build` (docs): `build: docs-only repo, no compilation required` (exit 0)
- `verify:web`: Next.js 15 production build OK + vitest 5/5
- `verify:api`: pytest 3 passed (grows with PBIs)
- `verify:parity`: A4 harness exit 0 offline (PBI-015+; live mode is an explicit flag, never in gates)
- `lint`: `lint: all contracts OK (N checks)` (exit 0)
- `test` (docs): 13 tests, 13 pass via `tests/smoke.test.js`

Prerequisites (one-time): `cd control-panel && npm install` and `python -m pip install -e ".[dev]"`. `npm run verify` is fully offline — no network, no Docker, no database. `docker compose up -d db` (pgvector Postgres 17) is for integration work only and is never part of the gate.

No PBI may start without a runnable gate. If tests are red, fix gates first. The docs-contract checks in `scripts/lint.js` / `tests/smoke.test.js` are a permanent regression gate — extend, never weaken.

Windows note (this environment): PowerShell 5.1, `.ps1` wrappers blocked. Use `cmd /c "npm.cmd ..."` / `npx.cmd` or `node` directly. Do not assume POSIX. Paths contain spaces — quote them.

## 3. Conventions

- **No change without a spec**: every PBI (including one-line fixes) requires a human-reviewed spec in `specs/{feature}/spec.md` or a compact behavior contract (2–4 sections) for bug fixes.
- **Micro-commits**: one logical change per commit, conventional messages (`feat:`, `fix:`, `docs:`, `chore:`, `test:`), never rewrite history.
- **Spec Reversing gate**: once code exists, reverse behavior specs before changing it; a documented bug must be caught in human review, not promoted to spec. (No code exists yet — this gate activates with the first code.)
- **POC reference policy** (founder decision 2026-09-13): the POC at `C:\Users\kcb19\Work\KCB\SWE-DRIP` (remote `kcbdev/SWE-DRIP-POC`) may be consulted as **reference** when planning/documenting/implementing hits a gap or needs a decision. Nothing from the POC is applied without **human validation** — no silent porting of code, schemas, or configs. Reference findings are recorded in the relevant spec/PBI with the validation outcome.
- **Brand invariants**: `#0D0D0D` void black, `#00FF41` terminal green, JetBrains Mono; no gradients, shadows, rounded pills, or pastels. No change without founder approval.
- **Price invariants**: $32 tee / $62 hoodie / $20 mug — enforced mechanically at the Shelf node, never per-product judgment.
- **Budget discipline**: OpenRouter cap ~$130/mo; break-even 4–5 shirt sales. Any PBI touching model routing or prompts must note cost impact.
- **Single source of truth**: the Control Panel reads through the LangGraph checkpointer and collection-contract YAML files — no parallel state copy (PRD NFR-1).
- **Context Map honesty**: update §5 when structure changes. Stale maps are worse than none.

## 4. Workflow (ASDLC loop)

1. `asdlc-plan` → produces `specs/{feature}/spec.md` + `tasks/PBI-*.md` + `plans/README.md` sequencing (from the delivery spec phases and/or Plane `Todo` issues)
2. `asdlc-execute` → Ralph Loop: implement → gates (`build`/`lint`/`test`) → adversarial + constitutional review → `In Review` vs `Done` sorting
3. `agentic` sorting (deterministic + no human judgment) may close to `Done` directly; `manual` (UX/product/security/production/live verification) stays `In Review` for the founder
4. Every transition out of `Active` carries `PBI-XXX`, `Branch`, `Commits`, `Review` type, and gate summary in the Plane comment

## 5. Context Map (Context Mapping practice)

Annotated YAML. Responsibilities per area, not file lists.

```yaml
project_structure:
  docs/:
    responsibility: "V1.0 spec kit — product definition, system design, and delivery contract. Source of truth until specs/{feature}/spec.md supersedes a feature's behavior."
    contains: "swe-drip-product-vision-v1.md (architecture + pipeline + collections), swe-drip-product-definition-v1.md (product/persona/pricing), swe-drip-prd-v1.md (Control Panel requirements), swe-drip-ux-spec-v1.md (screens + design system), swe-drip-technical-spec-v1.md (stack/architecture), swe-drip-data-api-llm-spec-v1.md (schemas/endpoints/model routing), swe-drip-delivery-acceptance-spec-v1.md (phases A1-A19), design ref/ (3 Control Panel HTML mockups)"
  docs/adrs/:
    responsibility: "Architecture Decision Records — structural decisions that change ARCHITECTURE.md."
    contains: "ADR-{NNN}.md per decision (ADR-001 = onboarding bootstrap)"
  specs/:
    responsibility: "Living specs — human-reviewed behavior contracts per feature (state). Overrides docs/ for that feature once created."
    contains: "15 feature specs (app-foundation, auth-rbac, audit-log, dashboard, pipeline-core, pipeline-runs, hitl-approvals, hitl-graduation, collections, design-qc, fourthwall-integration, traceability, catalog-analytics, settings-agents, agent-control-plane) — authored by asdlc-plan from the delivery spec phases; specs/{feature}/spec.md"
  tasks/:
    responsibility: "PBIs (deltas) — atomic, dependency-declared task cards derived from specs."
    contains: "PBI-{NNN}.md — populated by asdlc-plan"
  plans/:
    responsibility: "Sequencing and progress — PBI index, dependency graph, execution log, Plane Todo seed record."
    contains: "README.md (sequencing + Plane sync), PROGRESS.md (append-only log)"
  tests/:
    responsibility: "Deterministic verification — docs-contract smoke suite today; app test suites land with their PBIs."
    contains: "smoke.test.js (spec-kit invariants; extend per PBI, never weaken)"
  scripts/:
    responsibility: "Local tooling — gates and helpers that the verify chain invokes."
    contains: "build.js, lint.js"
  control-panel/:
    responsibility: "Next.js 15 (App Router) + shadcn/ui Control Panel — HITL approvals, run inspection, collections, audit, settings."
    status: "live scaffold (PBI-001); feature screens land per PBI"
  api/:
    responsibility: "FastAPI Control Panel API — RBAC, checkpointer read/write, audit writer, SSE stream, Fourthwall MCP client."
    status: "live scaffold (PBI-002); health route only"
  pipeline/:
    responsibility: "LangGraph StateGraph — 11-node pipeline, HITL interrupts, placement/colorway resolver, QC rubric."
    status: "live package placeholder (PBI-002); nodes land PBI-010+"
  collections/:
    responsibility: "Collection contract YAML files (/collections/<slug>.yaml) — the single source of truth for style/palette/colorways/placement/KPI thresholds."
    status: "live directory (PBI-003); YAML store lands PBI-019"

documentation_index:
  README.md:
    answers: "What is SWE Drip V1, what exists today, how do gates run, and where does knowledge live?"
  AGENTS.md:
    answers: "What is the stack, what are the gate commands, what are the conventions, and where does knowledge live (this Context Map)? Which Plane project is bound?"
  ARCHITECTURE.md:
    answers: "What is the as-built system today and the target architecture (modules, boundaries, data flow, constraints)?"
  docs/swe-drip-product-vision-v1.md:
    answers: "Why/how at system level: what 'full circle' means, the 11-node LangGraph pipeline, collection system, QC policy, roadmap, non-goals."
  docs/swe-drip-product-definition-v1.md:
    answers: "What are we selling, to whom: persona, value prop, launch collections, product scope, price invariants, success metrics, glossary."
  docs/swe-drip-prd-v1.md:
    answers: "What must the Control Panel do: roles, FR-1..FR-24, NFR-1..NFR-4, explicit out-of-scope."
  docs/swe-drip-ux-spec-v1.md:
    answers: "How the Control Panel looks and behaves: IA, key screens, interaction patterns, shadcn design system, accessibility."
  docs/swe-drip-technical-spec-v1.md:
    answers: "How it is built: components, frontend/backend choices, auth/RBAC, persistence, LangGraph + Fourthwall integration, hosting, security."
  docs/swe-drip-data-api-llm-spec-v1.md:
    answers: "Field names, endpoint shapes, Postgres tables, and per-node model routing."
  docs/swe-drip-delivery-acceptance-spec-v1.md:
    answers: "In what order it gets built and signed off: phases 1-7, acceptance criteria A1-A19, cross-cutting CC-1..CC-3."
  docs/adrs/ADR-{NNN}.md:
    answers: "Why a structural decision was made, alternatives, and consequences."
  specs/{feature}/spec.md:
    answers: "What is the human-reviewed behavior contract for that feature (state)?"
  tasks/PBI-{NNN}.md:
    answers: "What is the atomic delta to implement, its dependencies, and acceptance criteria?"
  plans/README.md:
    answers: "What is the PBI sequencing, dependency graph, and Plane Todo seed (bound to kcb/SWDRP)?"
  plans/PROGRESS.md:
    answers: "What has been executed, when, with what gate results and review types?"
```

## 6. Decisions

ADRs live in `docs/adrs/ADR-{NNN}.md`. ADR-001 records the onboarding bootstrap (clean-room V1, Plane binding, gate baseline, POC reference policy).

## 7. Verification

See §2. Baseline 2026-09-13 (post PBI-001…003): docs build OK, lint OK, 13/13 smoke tests; Control Panel build OK + vitest 5/5; pytest 3 passed; Plane binding verified via MCP `plane-kcb`. Evidence is re-runnable with `cmd /c "npm run verify"`.

## 8. Plane binding

- Workspace: `kcb` (MCP: `plane-kcb`)
- Project: `SWE DRIP` — `d162b6d4-1205-4eea-9ef3-871354c5e8a3` (identifier `SWDRP`)
- Verification: `plane-kcb` project list returns `SWDRP` — verified 2026-09-13 via MCP
- Sync scope: strictly `kcb/SWDRP`; `Backlog` ignored until moved to `Todo`; issues route through `asdlc-plan` for Spec/PBI authoring
- Note: the retired POC is a separate project — `kcb/SWDR (2af62f36-...)` — never synced from this repo
