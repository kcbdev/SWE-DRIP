# ARCHITECTURE.md — SWE Drip V1 (as-built, not gospel)

> **Status: as-built snapshot 2026-09-13 — docs-only repo, no runtime code yet.** Sections marked **Target** describe the intended system from the v1.0 spec kit; they are not built. This document is not a prescription — change it via ADR (`docs/adrs/ADR-NNN.md`). Dead structure found later is corrected **here**, not silently in code.

---

## 1. System overview

**As-built:** this repo contains the v1.0 spec kit (`docs/`), the constitution (`AGENTS.md`), this architecture snapshot, and a zero-dependency Node 22 docs-contract gate (`npm run verify`). No application code exists yet.

**Target** (from `docs/swe-drip-technical-spec-v1.md` §1):

```
Control Panel (Next.js 15 + shadcn/ui)
  Dashboard · Collections · Approvals · QC · Catalog · Agents · Analytics · Audit · Settings
        │ REST (auth'd)                       │ SSE (live run status)
        ▼                                      ▼
Control Panel API (FastAPI)
  Auth + RBAC · checkpointer read/write · collection-contract YAML read/write
  audit writer (every state-changing call) · Fourthwall MCP client (reads)
        │                    │                    │
        ▼                    ▼                    ▼
Postgres (checkpointer,   LangGraph engine    Fourthwall MCP (reads) +
audit log, users/roles)   (11-node pipeline,  hand-rolled Open API (writes,
                          interrupt/resume)   pending the §4 spike decision)
```

- **Custom build**: no Paperclip/Hermes in the runtime (Vision doc §3.1). The POC is retired for the core pipeline.
- **Single source of truth**: Control Panel reads through the same LangGraph Postgres checkpointer and `/collections/<slug>.yaml` contracts the pipeline uses — no parallel state copy (PRD NFR-1, Technical Spec §6).
- **Storefront**: Fourthwall owns catalog/cart/checkout/payments end-to-end. This repo never builds storefront UI or payment code.

## 2. As-built modules

| Module | Path | Form | Responsibility | Status |
|---|---|---|---|---|
| **Spec kit** | `docs/*-v1.md`, `docs/design ref/*.html` | Markdown + HTML | Product vision/definition, PRD, UX, technical, data/API/LLM, delivery/acceptance; 3 Control Panel mockups | **Live** — source of truth |
| **Constitution** | `AGENTS.md` | Markdown + YAML Context Map | Stack, gates, conventions, workflow, Context Map, Plane binding (`kcb/SWDRP`) | **Live** |
| **Architecture snapshot** | `ARCHITECTURE.md` | Markdown | As-built + target modules, boundaries, data flow, constraints | **Live** |
| **Verification harness** | `tests/smoke.test.js`, `scripts/lint.js`, `package.json` | Node 22 + `node:test` | 13-test spec-kit smoke suite + docs-contract lint (binding, Context Map, no secrets); `npm run verify` is the Ralph Loop gate | **Live** — 13/13 passing |
| **Decisions** | `docs/adrs/ADR-{NNN}.md` | Markdown | Structural decisions (ADR-001 = onboarding bootstrap) | **Live** |
| **Planning artifacts** | `specs/`, `tasks/`, `plans/` | Markdown + YAML | Feature specs, PBIs, sequencing/progress | **Empty** — populated by `asdlc-plan` |
| **Control Panel** | `control-panel/` (planned) | Next.js 15 + shadcn/ui | HITL approvals, runs, collections, audit, settings | **Target** |
| **Control Panel API** | `api/` (planned) | FastAPI | RBAC, checkpointer access, audit writer, SSE, Fourthwall MCP reads | **Target** |
| **Pipeline** | `pipeline/` (planned) | LangGraph `StateGraph` | 11 nodes, `interrupt()`/`Command(resume=...)`, placement/colorway resolver, QC rubric | **Target** |
| **Collection contracts** | `collections/` (planned) | YAML | `/collections/<slug>.yaml` — style/palette/colorways/placement/KPI thresholds | **Target** |

Planned layout is indicative; the scaffold PBI fixes it (ADR required if structural).

## 3. Boundaries & dependencies

```
docs/ (spec kit, source of truth)
   └─► specs/{feature}/spec.md (human-reviewed; overrides docs/ per feature)
          └─► tasks/PBI-*.md ──► plans/README.md ──► asdlc-execute ──► control-panel/ + api/ + pipeline/
                                   │
                                   └─► tests/*.test.js + extended app gates (gates prove contract)
```

Target runtime boundaries:
- Control Panel API is the only backend the frontend talks to; it owns auth/RBAC, audit writes, and pipeline control (approve/reject → `Command(resume=...)`).
- Product creation is pipeline-owned (FW-create node) only — no second write path from the Control Panel (CC-2).
- HITL gates are LangGraph `interrupt()` state, not a custom approval queue (Technical Spec §6).
- Fourthwall and OpenRouter credentials are server-side only, never in the frontend.
- Existing Coolify/Hetzner infra hosts everything — no new provider.

## 4. Data flows (target pipeline, Vision doc §3.2)

```
 1 Trend research + clustering   deterministic scoring (>=60) + thematic clustering      HITL off
 2 Collection contract approval  CEO reviews clustered briefs, locks contract             HITL ON
 3 Listing copy                  slogan/title/description/tags                            off
 4 Design spec                   brief resolved against active collection contract        off
 5 Art render                    image generation against resolved spec                  off
 6 Placement & colorway          deterministic: contract + design type -> zones/colorways off
 7 Aesthetic QC                  vision rubric (cohesion/focal/placement/contrast)        HITL ON (until calibrated)
 8 Technical QC                  RGBA/dimension/transparency validation                  off
 9 Fourthwall product create     MCP write where coverage matches; else hand-rolled API   —
10 Publish gate                  final review before state: PUBLIC                        HITL ON
11 Shelf                         price invariants ($32/$62/$20) + collection assignment   off
```

Every node is implemented with `interrupt()` capability from the start; HITL on/off is a config flag, never a structural rebuild (Vision doc §3.1).

## 5. Known constraints & risks

| Constraint | Impact | Mitigation |
|---|---|---|
| **No code yet** — docs-only repo | Nothing executable beyond gates; Spec Reversing not yet applicable | First code PBI extends gates with real runner (Next.js/pytest); Spec Reversing activates with code |
| **POC retirement** — Paperclip/Hermes live products exist (EXIT 0, UNTIL USER 50) | Migration must not disturb live selling | Publish step cut over last, after parity validation (Vision doc §3.1) |
| **Model override bug in POC** (Hermes gateway forced one model for all nodes) | Same failure must not recur | Per-node model IDs in code/config; gate asserts routing table (Data spec §3) |
| **Fourthwall write coverage unknown** | Product-create mechanism undecided | Spike before committing (Vision §4); decision recorded with evidence |
| **Image-model quality bounds** | QC gate catches failures, doesn't fix model limits | Aesthetic QC rubric + capped regeneration loop; HITL stays on until calibrated on real outcomes |
| **Budget $130/mo cap** | Runaway prompt/model changes can breach cap | Cost logged per call `{node, model, tokens_in, tokens_out, cost_usd}`; Dashboard warning above 80% |
| **Windows PowerShell 5.1 env** | `.ps1` wrappers blocked | `cmd /c "npm.cmd ..."`; no POSIX assumptions; quote paths (repo path contains a space) |
| **HITL graduation is data-driven** | No calendar shortcut to autonomy | Calibration log (human vs rubric) per UX §3.3/FR-14; Phase 7 review decides with evidence |

## 6. Decision log

| ADR | Decision | Status |
|---|---|---|
| [ADR-001](docs/adrs/ADR-001.md) | Clean-room V1 bootstrap: custom stack, `kcb/SWDRP` binding, docs-contract gates, POC as reference-only | Accepted 2026-09-13 |

## 7. Verification

Baseline 2026-09-13:
- `cmd /c "npm run build"` → `build: docs-only repo, no compilation required` (exit 0)
- `cmd /c "npm run lint"` → `lint: all contracts OK` (exit 0)
- `cmd /c "npm test"` → 13 tests pass via `tests/smoke.test.js`
- Plane binding verified via `plane-kcb` MCP: workspace `kcb`, project `d162b6d4-1205-4eea-9ef3-871354c5e8a3 (SWDRP)`
- Plane `Todo` seed: 0 issues at onboarding
