# Spec: Audit Log

## Goal

Provide the append-only, actor-bound audit trail behind PRD §3.7 (FR-20/21/22): every state-changing action is logged with actor, timestamp, and before/after values; the log is filterable, exportable, and sufficient on its own to reconstruct why any publish/price/approval decision happened.

## Scope

- In scope: `audit_log` schema; a single write path used by every state-changing API call; auth-event rows (login/logout); read API with filters + export; Audit Log screen with diff rendering.
- Out of scope: log shipping to external systems; tamper-proofing beyond DB grants; UI for editing anything (impossible by design).

## Contracts (success criteria)

- **C1 — Append-only by construction**: every state-changing API call writes its audit row atomically with (or before) the action; there is no application code path that updates or deletes an audit row.
- **C2 — Actor binding**: every row carries an authenticated actor; system-initiated writes use an explicit `actor_user_id` of the designated system principal — never null-by-accident.
- **C3 — Filterable + exportable**: the read API filters by actor, action, entity type/id, and date range; the filtered set is exportable (CSV or JSON download).
- **C4 — A2 evidence**: login, logout, role change, and settings change each produce a row with the correct actor, timestamp, action, and entity (deterministic tests for role/settings changes; auth events verified in integration).
- **C5 — Chain reconstruction (FR-22)**: entity references are standardized (`entity_type`/`entity_id` + before/after JSON) so a product's brief → contract → QC → approver → publish chain is reconstructable from the audit log alone.
- **C6 — No secrets**: audit payloads never contain credentials, tokens, or session material.

## Anti-patterns

- Writing audit rows from anywhere but the designated writer (API helper / auth hook).
- Mutable rows, "correction" updates, or silent deletions.
- Storing full secret-bearing request bodies as `before/after`.
- A UI that hides actions from the log (every state change must appear, including failed approvals? — no: only state changes; failed/no-op actions are not rows).

## Decisions

- Auth events (login/logout) are written by the Better Auth hook inside `control-panel/` using the same `audit_log` schema; all other writes go through the FastAPI writer. Schema is the shared contract.
