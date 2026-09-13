# Spec: Pipeline Core

## Goal

Implement the locked 11-node product pipeline (Vision doc §3.2) as a LangGraph `StateGraph` with a Postgres checkpointer, per-node OpenRouter model routing, cost logging, deterministic placement/colorway resolution, aesthetic + technical QC, and HITL gates built in as `interrupt()` with config flags — the custom replacement for the retired Paperclip/Hermes pipeline (A4–A6).

## Scope

- In scope: pipeline state schema (design record per data spec §1.3); all 11 nodes in order; OpenRouter client (LLM + image + vision); routing table as the single model source; cost logging to `model_calls`; Postgres checkpointer wiring (memory checkpointer for tests); parity harness (offline, mocked) comparing output shapes for brief samples; publish step left uncut (FW create stays DRAFT-only).
- Out of scope: Control Panel UI for approvals/QC/runs (their specs); Fourthwall publish cutover (fourthwall-integration spec, Phase 5); rubric calibration against known examples (design-qc spec); resume API surface (hitl-approvals spec).

## Contracts (success criteria)

- **C1 — State schema**: run state carries the design record shape from data spec §1.3 (`design_id, collection_id, brief, render, qc_scores, placement`) plus node-level intermediates; queryable per node from the checkpointer.
- **C2 — 11 nodes, config-driven HITL**: the graph executes nodes in the locked order; every node is `interrupt()`-capable from the start; HITL on/off is a config flag (collection contract / node config), never a structural branch.
- **C3 — Per-node routing**: each node calls its designated model directly per the data spec §3 table; `pipeline/routing.py` is the single source of model IDs; no gateway/override layer exists or may be added.
- **C4 — Cost logging**: every model call logs `{node, model, tokens_in, tokens_out, cost_usd}` to `model_calls`; a logging failure is recorded and surfaced, never silently swallowed or crash-inducing.
- **C5 — A5**: a full run's checkpointer state is inspectable and matches the design record schema.
- **C6 — A6**: a deterministic test proves the actual model ID used per node equals the routing table entry (mocked client captures call params).
- **C7 — A4 (offline parity)**: the parity harness runs brief samples through the graph with mocked model calls and asserts output shapes match the expected pipeline shapes (clustered brief set → collection contract shape; design brief → design spec shape); the publish step remains uncut (no `PUBLIC` products).
- **C8 — Deterministic placement/colorway**: resolution is a pure function of (collection contract, design type) → placement zones + contrast-valid colorways; no model calls.
- **C9 — QC policy**: aesthetic QC scores the four rubric criteria (style-cohesion, focal-point, placement-fit, contrast) with a 70 pass threshold and a capped regeneration loop that feeds rejection notes back into the next render prompt; technical QC validates RGBA/dimensions/transparency.
- **C10 — Shelf invariants**: price check enforces $32/$62/$20 mechanically before any Fourthwall write; collection assignment requires an active, non-retired contract.

## Anti-patterns

- A shared gateway payload/template that can silently override per-node models (the POC's known bug).
- Per-design creative decisions that bypass the locked collection contract.
- Publishing (`state: PUBLIC`) from this phase — cutover is Phase 5 and gated.
- Model calls outside the routing table; nodes skipping cost logging.
- Implementing HITL as graph-structural branches instead of `interrupt()` + config flags.
- Calling live models or Fourthwall in deterministic gates (mock everything).

## Decisions

- Pipeline executes in-process within the API deployable (ADR-002); extraction to a worker is ADR-gated.
- FW-create node is DRAFT-only until the fourthwall-integration cutover; publish gate node exists but cannot publish publicly in this phase.
- Routing table lives in code (`pipeline/routing.py`), mirroring data spec §3; changing a model is a config edit reviewed against budget impact.
