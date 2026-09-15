# Spec: Pipeline Runs (run initiation)

## Goal

Give the pipeline an **entry point**. Before this spec, the 11-node graph could only be *replayed* or *resumed* — `build_graph().invoke()` existed solely in tests and the parity harness, so no run could ever be started in production and A7/A14/A17/A18 were structurally unreachable.

## Scope

- In scope: starting a new pipeline run from the Control Panel API (Admin/Operator), configured entirely from the running system's own state (settings store, collection contracts, checkpointer), with cost discipline and a hard phase lock against storefront writes.
- Out of scope: the Fourthwall publish cutover (PBI-027) and the write client it injects; scheduled/automatic runs; re-triggering a *specific node* (that is FR-10 replay, already shipped); any new run-state store.

## Contracts (success criteria)

- **C1 — Start**: `POST /api/runs` (Admin/Operator) accepts `{collection_id, design_id?, briefs?}` and starts a new run, returning `202` with `{run_id, status, collection_id, design_id}`. The run is visible in `GET /api/runs` and `GET /api/runs/{run_id}` immediately, with no other action taken.
- **C2 — Single source (NFR-1)**: the run's state lives only in the LangGraph checkpointer. `run_id` **is** the checkpointer `thread_id`; no parallel run record is written anywhere.
- **C3 — Config from the live system**: HITL flags come from the settings store (the same source the Settings UI writes), and the collection contract is read from the YAML store. Toggling a gate remains a config change, never a graph rebuild (pipeline-core C2).
- **C4 — Cost discipline**: the run is refused (`409`, naming month-to-date spend and the cap) when spend already meets or exceeds the global monthly cap (AGENTS.md §3, $130). Every model call the run makes is written to `model_calls` — a run that cannot record cost is a run whose cost is invisible, so the cost engine is always configured.
- **C5 — Phase lock (safety)**: run-start never sets `fw_live` and never injects a Fourthwall **write** client. Nothing reachable from this endpoint can create or publish a storefront product; node 9 records an explicit error instead. Publishing stays gated behind PBI-027.
- **C6 — Audited**: a `run.start` audit row records the actor, the run id, the collection, and the HITL flags the run was started with (presence/flags only — never secrets).
- **C7 — Non-blocking**: the graph executes off the request thread, so the response does not wait for the run to pause or finish. Long-running work never holds an HTTP connection open.

## Anti-patterns

- Starting runs from a Viewer session, or any client-side attempt at gating (the API is the enforcement point).
- Waiting synchronously for the whole graph; a run that pauses at a gate or takes minutes must not block a request.
- Enabling live Fourthwall writes from the start path, or as a side effect of a default.
- Writing run status to a second store (Postgres row, YAML, JSON file) instead of reading the checkpointer.
- Silently starting a run when the budget cap is already exceeded.

## Decisions

- **Explicit start, not implicit-on-approve.** Approving a collection candidate keeps its current meaning (atomic active-stamp + best-effort resume of a *paused* run). Starting is a separate, explicit action, so an approval can never spend money as a side effect. Amend this spec's Decisions before coupling the two.
- **`briefs` are REQUIRED, not optional** (revised 2026-09-15 by the first live run). Node 1 clusters briefs into candidates, and each brief must carry the locked score fields `engagement` (0–40), `novelty` (0–30), `specificity` (0–30). An empty set silently yields zero clusters, which cascaded into eight downstream node errors and a run that could never reach a gate — so the API rejects it up front with a single actionable 422. Ranges are read from `pipeline/nodes/trend.py`, never re-declared. The canonical shape is `pipeline/tests/fixtures/briefs_sample_a.json`.
- **`design_id` defaults to the run id.** A run needs a `design_id` for its render artifact path and state record; when the caller does not supply one, the generated run id is used so the value is stable and unique without invention.
- **Cap policy is a refusal, not a warning.** The cap is a stated invariant (AGENTS.md §3); the remedy is to raise it in Agents → budget caps, so a refusal is actionable rather than a silent overspend. If month-to-date spend cannot be read at all, the start is refused (`503`) rather than assumed to be zero.
