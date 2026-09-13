# Spec: HITL Graduation

## Goal

Close the autonomy loop with data, not vibes: a documented decision per HITL gate — kept on or turned off — backed by calibration data and publish history (Vision §6.4, A19). This is a review deliverable, not a code feature.

## Scope

- In scope: a graduation review record per gate (collection approval, design QC, publish gate) with evidence references; the checklist that must be satisfied before any default flips; the decision log entry.
- Out of scope: the config mechanism that flips a toggle (settings spec/PBI-033); changing thresholds or rubric versions (their specs); re-opening Phase 4 calibration (design-qc).

## Contracts (success criteria)

- **C1 — A19 record**: for each HITL gate, a decision artifact (kept on / turned off) exists with explicit supporting data references — calibration agreement stats (A11), publish-gate history, and any incident notes. No unilateral toggle without the record.
- **C2 — Evidence minimums**: a gate may only be turned off when its phase's evidence minimums are met (e.g. design QC: human-vs-rubric calibration on at least N designs; publish gate: zero post-publish corrections attributed to missed review over the observation window). The exact N and window are fixed in the record, not improvised.
- **C3 — Founder authority**: the decision is founder-signed; the agent assembles evidence and drafts the record, but the flip is a human judgment with an audit trail.
- **C4 — Reversibility**: the record states the revert condition (metric degradation, incident) that returns the gate to on — implemented via the settings mechanism, no code change.
- **C5 — Traceability**: the decision references audit rows/calibration queries so a later reader can reproduce the evidence.

## Anti-patterns

- Turning off a gate because "it seems fine" without the evidence minimums.
- Using calendar time as a substitute for data volume/quality.
- Editing calibration records or thresholds to make the numbers pass.
- A graduation that cannot be reverted by config alone.

## Decisions

- Graduation is assessed gate-by-gate; a mixed outcome (e.g. QC off, publish on) is expected and valid.
- The record lives in `plans/PROGRESS.md` (resolution) with the full artifact under `docs/` if it grows beyond a table — no new system.
