# Plans — SWE Drip V1

> Sequencing index for `asdlc-plan` / `asdlc-execute`. One PBI per task card; dependency graph drives Ralph Loop order. **No PBIs yet** — the spec kit is onboarded; feature planning starts with `asdlc-plan` against `docs/swe-drip-delivery-acceptance-spec-v1.md` (Phases 1–7) and the Plane `Todo` queue.

## Plane sync

Bound to Plane: **kcb / SWDRP (d162b6d4-1205-4eea-9ef3-871354c5e8a3)** — verified via MCP `plane-kcb` 2026-09-13.
Backlog ignored until moved to `Todo` — only `Todo` issues are candidate feature inputs.

- 2026-09-13: onboarding seed pull — **0 `Todo` issues found** (project created same day; no candidate inputs yet)
- Next sync: `asdlc-plan` pulls `Todo` before authoring PBIs; `asdlc-plane` strictly scoped to `kcb/SWDRP`

## Sequencing

_Empty — populated by `asdlc-plan`._ Expected first derivation: Delivery Spec Phase 1 (Control Panel foundation: auth + RBAC, users/roles, audit log, dashboard skeleton), Phase 2 (LangGraph pipeline migration) planned in parallel where dependencies allow.

| Order | PBI | Spec | Depends on | State | Plane | Files (blast radius) |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

## How to add a PBI (via asdlc-plan)

1. Move the Plane issue to `Todo` (or create one) — `asdlc-plane` syncs it as a candidate input
2. Run `asdlc-plan` — it writes `specs/{feature}/spec.md` + `tasks/PBI-XXX.md`
3. `asdlc-plan` updates this table with the PBI and its dependencies
4. `asdlc-execute` picks the next `Todo` PBI, moves it to `In Progress`, and runs the Ralph Loop

## Gate plan (all PBIs)

- Deterministic (must pass before `In Review`): `cmd /c "npm run verify"` → build && lint && test
- App-stack PBIs extend the gates (Next.js build/test, pytest) and update `AGENTS.md` §2 — the docs-contract checks stay as a regression gate, never weakened
- Review: adversarial + constitutional (brand/price/budget invariants, Context Map honesty) per `asdlc-execute`
- Manual sorts (founder): anything touching live Fourthwall, production infra, credentials, or UX decisions

## Spec Reversing reminder

No code exists yet, so every upcoming PBI is greenfield. Once code lands, a change to existing behavior requires a reversed, human-reviewed spec (`specs/{feature}/spec.md`) before implementation — bugs documented as features are defects.
