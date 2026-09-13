# Spec: HITL Approvals

## Goal

Make every human-in-the-loop gate (collection contract approval, design QC, publish gate) actionable from one aggregated Control Panel queue, with decisions mapped directly to LangGraph `Command(resume=...)` against the paused run — no parallel approval data model, no SSH/YAML hand-editing (FR-11, A7, Technical Spec §6).

## Scope

- In scope: `hitl_approvals` index table; resume service; aggregated queue API; decision API (approve/reject/regenerate + note); SSE live updates; Approvals screen.
- Out of scope: gate-specific detail screens (design-qc and collections specs own those); notification channels (email/Telegram); changing the gates themselves (pipeline-core).

## Contracts (success criteria)

- **C1 — One queue**: every open gate appears in `GET /api/approvals` with run id, node, entity reference, and waiting-since; sourced from the checkpointer's interrupt state + the thin `hitl_approvals` index — never a duplicated approval model.
- **C2 — Decision → resume**: approve/reject/regenerate produces exactly one `Command(resume=...)` per decision; the endpoint is idempotent (a duplicate submission returns the recorded decision and never double-resumes).
- **C3 — A7**: a clustered brief set awaiting the collection gate is visible in the queue and approvable/rejectable entirely from the Control Panel — no file edits, no direct API calls outside the UI.
- **C4 — Audited**: every decision writes an audit row (actor, action, entity, note, before/after) through the shared writer.
- **C5 — Live**: `GET /api/stream/runs` (SSE) pushes run-status and queue deltas; the UI reflects "resuming pipeline…" until the backend confirms.
- **C6 — RBAC**: Viewer+ may read the queue; Admin/Operator required for decisions; enforced server-side.

## Anti-patterns

- A custom approval-queue table that can drift from interrupt state.
- Polling as the primary update mechanism for the queue/dashboard.
- Non-idempotent decision handling (double resume, lost decisions).
- Missing audit rows on any decision, including rejections and regenerate requests.
- UI-only role gating.

## Decisions

- SSE over WebSocket: pushes are unidirectional; approvals are POSTs (Technical Spec §2 allows either; SSE chosen for simplicity).
- `hitl_approvals` is an index for querying/filtering — the LangGraph interrupt remains the source of truth for gate state (NFR-1).
