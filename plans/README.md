# Plans — SWE Drip

> Sequencing index for `asdlc-plan` / `asdlc-execute`. One PBI per task card; dependency graph drives Ralph Loop order.

## Plane sync

Bound to Plane: **kcb / SWDR (2af62f36-c11a-411a-89b5-8e5a5176b829)** — verified via MCP `plane-kcb` 2026-08-22.
Backlog ignored until moved to `Todo` — only `Todo` issues are candidate feature inputs.

- Todo issues seeded on 2026-08-22: **0 — no Todo issues found** in `kcb/SWDR`
- Next sync: `asdlc-plan` will pull `Todo` before authoring Specs/PBIs

## Sequencing

No PBIs yet. This is the onboarding bootstrap — `specs/` and `tasks/` are empty by design.
Feature work routes through `asdlc-plan`: it reverses a human-reviewed spec (see AGENTS.md §B — Spec Reversing gate) then emits `specs/{feature}/spec.md` + `tasks/PBI-{NNN}.md` + sequencing here.

| Order | PBI | Feature | Depends on | State | Plane |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

_Add rows as `asdlc-plan` produces PBIs. Keep this table sorted by execution order._

## Dependency graph

```
(onboarding bootstrap) → asdlc-plan (PBI-001 …) → asdlc-execute (Ralph Loop: build/lint/test → review → Done)
```

## How to add a PBI (via asdlc-plan)

1. Move Plane issue to `Todo` (or create one) — `asdlc-plane` syncs it here as candidate
2. Run `asdlc-plan` — it writes `specs/{feature}/spec.md` and `tasks/PBI-XXX.md`
3. `asdlc-plan` updates this table with the PBI and its dependencies
4. `asdlc-execute` picks the next `Todo` → `In Progress` PBI and runs the Ralph Loop

## Spec Reversing reminder

Never start a PBI on brownfield code without a reversed, human-reviewed Spec (`specs/{feature}/spec.md` — behavior, not code narration). Bugs documented as features are defects.
