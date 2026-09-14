# Spec: Collections

## Goal

Make collection contracts the operated, single-source unit of creative strategy: YAML files at `/collections/<slug>.yaml` (data spec §1.1) listed, authored, approved, edited, and retired entirely from the Control Panel — including candidate surfacing from Trend clusters and the survivor-product exception (FR-4..7, A8, A9).

## Scope

- In scope: YAML store (validated read/write, atomic, mtime-guarded); CRUD + lifecycle API; candidates from clustered briefs; approve/retire with survivor exception; Collections screens (list, detail, create/edit).
- Out of scope: contract generation inside the graph (pipeline-core owns drafting); retirement recommendations from KPI data (catalog-analytics); the aggregated approvals queue mechanics (hitl-approvals).

## Contracts (success criteria)

- **C1 — YAML is the single source**: contracts live only as `/collections/<slug>.yaml`, schema-validated; Postgres indexes nothing beyond references; manual file edits are detectable (mtime mismatch flagged), never silently authoritative.
- **C2 — CRUD**: list filterable by status (draft/active/retired); detail with contract fields; create draft and edit fields via forms (Admin for create/edit) — no raw-YAML editing required anywhere in the flow.
- **C3 — Candidates + A8**: clustered brief groups surface as draft candidates; approval (Admin/Operator) produces a schema-valid contract YAML with `status: active` and `approved_at`, reflected in the list immediately.
- **C4 — A9 retire + survivor**: retirement marks the contract retired while excepted products stay live and flagged; verified against a concrete test case.
- **C5 — Audited**: create, edit, approve, retire each write an audit row (actor, before/after).
- **C6 — Validation**: schema-invalid contracts are rejected with field-level errors; unknown fields fail, not silently pass.

## Anti-patterns

- Duplicating contract content into Postgres tables.
- Requiring SSH/file edits for any lifecycle action (NFR-2).
- Retiring a collection without honoring the survivor exception path.
- Silent acceptance of malformed YAML or unknown keys.
- Editing a contract that a paused pipeline run is actively resolving against without flagging the conflict.

## Decisions

- Approval stamps `approved_at` and sets `status: active` in one atomic write.
- Candidates are draft contracts pre-filled from the cluster's fields; the CEO may edit before approving.
- The store module (`api/app/collections_store.py`) is the only filesystem writer for `/collections`; the dashboard's earlier inline glob may be refactored onto it without changing response shapes.
- **2026-09-14 (PBI-020)**: the A9 survivor exception is persisted as optional `survivor_products: [product_id]` on the retired contract (absent/empty when none). Data spec §1.1 carries no survivor field, so this is additive schema, not a silent invention: the catalog mirror (PBI-030) reads it to keep those products live and flagged. Completeness gate at approve time: non-empty `illustration_rules.palette` + all three `kpi_thresholds` set (pipeline drafts carry explicit placeholders until the CEO edits them).
