# Spec: Dashboard

## Goal

Answer "what needs my attention right now" in under five seconds of scanning (FR-1/2/3, A3): pipeline health at a glance, monthly AI spend vs the $130 cap, active-collection KPI status, recent activity, and the top of the approvals queue — all read through real endpoints, never fabricated.

## Scope

- In scope: `GET /api/dashboard/summary` (counts, spend, collections status, recent activity, pending top items); Dashboard screen (stat cards, activity feed, pending list).
- Out of scope: approvals actions (hitl-approvals spec), run-level detail (traceability spec), per-collection KPI charts (catalog-analytics spec), writing any state.

## Contracts (success criteria)

- **C1 — Stat cards**: runs/pending-approvals count; monthly spend vs $130 cap with a visible warning state above 80%; active collections count with an at-risk flag when any KPI is below threshold.
- **C2 — A3 is a real data path**: the dashboard displays spend and active-collection count without manual data entry; before producing phases land it renders honest empty states (zeros only when the source is truly empty).
- **C3 — Activity feed**: last N events (renders, QC outcomes, publishes, retirements, audit-worthy config changes) with relative timestamps and links to their entity views when those exist.
- **C4 — One approvals source**: the pending-approval list reads the same data source as the Approvals queue (no parallel approval model).
- **C5 — No fabricated data**: unavailable/failed sources show explicit error/empty states, never placeholder numbers.

## Anti-patterns

- Hardcoding fixtures or demo numbers in the UI.
- Creating a second state store for approvals/runs/spend.
- The dashboard performing writes or triggering pipeline actions.
- Amber warning styling leaking into non-warning UI (brand: terminal green accent, amber reserved for warnings).

## Decisions

- **A3 sign-off sequencing**: the Phase-1 PBI proves the real data path (endpoints + empty states). Full A3 evidence with non-empty data is signed off once pipeline-core (cost rows) and collections (contracts) have produced real data; recorded as a sequencing note in the PBI resolution.
- The `model_calls` cost table migration is owned by this spec's API PBI (PBI-008); the pipeline writes rows through `pipeline/costs.py` from pipeline-core.
