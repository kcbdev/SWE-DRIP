# Spec: Design QC

## Goal

Make the aesthetic QC gate reviewable and trustworthy: rubric scoring surfaced next to the render with all four criteria, valid/invalid colorways, approve/reject/regenerate with feedback, and a human-vs-rubric calibration trail — the evidence base for eventually graduating this gate (FR-12..14, A10–A12, Vision doc §6).

## Scope

- In scope: rubric validation suite against the known examples; design-detail API (render + scores + placement + run context); calibration trail (human decision vs rubric verdict, derived from existing records); Design QC screen.
- Out of scope: rubric scoring implementation and regeneration loop mechanics (pipeline-core PBI-013); generic approvals queue mechanics (hitl-approvals); HITL graduation decision itself (hitl-graduation spec).

## Contracts (success criteria)

- **C1 — A10**: the known negative example (mixed-style "ninja") scores below the 70 threshold and the known positive (rocket) above it, without hand-tuning targeted at those specific images; evidence is a deterministic validation suite (pinned model responses/fixtures) plus a manual live-run script for the same assertion.
- **C2 — Design detail API**: returns render reference, four rubric scores + threshold + pass/fail result, placement and contrast-valid colorways, and run context (brief, collection contract) for a design id.
- **C3 — A12**: regeneration requested with a rejection note produces a materially different next render prompt (not a no-op retry); the note is carried into the regeneration payload.
- **C4 — A11 — calibration trail**: every human decision is recorded side-by-side with the rubric verdict for that design (derived from decision records + run scores — no duplicate store), so agreement can be reviewed before graduation.
- **C5 — QC screen**: large render preview; four score bars with the threshold marked; colorway swatches showing valid vs invalid (contrast-fail reason on hover); approve / reject-with-note / regenerate actions; a calibration indicator comparing this design's human decision with what the rubric alone decided.
- **C6 — Decisions**: audited and idempotent through the HITL mechanism (no separate decision path).

## Anti-patterns

- Hard-coding the known examples' outcomes or tuning the rubric per-example.
- Reject without a note (the note feeds regeneration).
- Computing calibration client-side instead of from recorded decisions/scores.
- A second decision endpoint outside the HITL mechanism.
- Changing the pass threshold (70) without a spec amendment.

## Decisions

- `rubric_version` is stored with scores so calibration stays interpretable if the rubric prompt changes.
- Calibration is derived by joining `hitl_approvals` decisions with run-state QC scores — the LangGraph checkpointer remains the score source (NFR-1).
