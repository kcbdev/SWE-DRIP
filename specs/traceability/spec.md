# Spec: Traceability

## Goal

Surface the LangGraph checkpointer as the run-inspection surface: list runs, inspect any node's recorded state, and replay from a chosen node using only recorded upstream state (FR-8/9/10, A16, A18) — the traceability differentiator over "just check the database."

## Scope

- In scope: runs list + detail API (per-node state history); replay-from-node API; Runs screens (list, step tracker, node inspector, replay action).
- Out of scope: dashboard activity feed (dashboard spec); design QC review (design-qc spec); audit log viewer (audit-log spec); any write into run state other than replay execution.

## Contracts (success criteria)

- **C1 — Runs list**: filterable by collection, status, and date; each row shows current node, status, started/updated timestamps.
- **C2 — Run detail**: a horizontal step tracker matching the locked 11-node order (Vision §3.2); each node expands to its recorded state at that point, read from the checkpointer — not copied into another store.
- **C3 — A18 replay**: replay-from-node resumes using only the recorded upstream state; a test proves earlier nodes are not re-executed.
- **C4 — A16 chain**: for a live product, the full causal chain (brief → contract → QC scores → approver → publish) is reconstructable from the Control Panel alone.
- **C5 — Authorization + audit**: replay is Admin/Operator; every replay writes an audit row with the source node.
- **C6 — Single source**: no duplicate run-state model; the checkpointer is the only state source (NFR-1).

## Anti-patterns

- Copying per-node state into Postgres "for the UI."
- Replay that silently re-runs upstream nodes or mutates prior history.
- Replay without an audit row or without role enforcement.
- A step tracker with a different node order than the locked pipeline list.
- Exposing raw checkpointer internals to the client (typed views only).

## Decisions

- Replay leverages the checkpointer's resume-from-state capability; no custom re-run engine.
- Node display order is fixed to the Vision doc §3.2 eleven-node list; the UI must fail loudly if the graph's node set diverges.
