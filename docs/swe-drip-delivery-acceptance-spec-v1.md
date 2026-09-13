# SWE Drip — Delivery / Acceptance Specification v1.0

*Phases the full document set (Vision, Product Definition, PRD, UX Spec, Technical Spec, Data/API/LLM Spec) into buildable increments, with explicit acceptance criteria per increment. Aligns with the roadmap already set in the Vision doc (§7) but adds the Control Panel work introduced afterward.*

---

## 1. Delivery philosophy

Each phase must leave the system in a working state — no phase depends on "finish everything, then test." The pipeline migration and the Control Panel build run in parallel where possible, since the Control Panel's early value (traceability, dashboard visibility) doesn't require the LangGraph migration to be complete — it can start against the *current* Paperclip/Hermes system's data and be extended once the migration lands.

## 2. Phases

### Phase 1 — Control Panel foundation (parallel to pipeline migration)
**Scope:** Auth + RBAC, Users/Roles screen, Audit Log (writing + viewing), Dashboard skeleton (spend vs. cap, using current Paperclip cost data even if imperfect per the known "Observed spend field: 0" gap).
**Acceptance criteria:**
- A1: Three roles (Admin/Operator/Viewer) enforced server-side, verified by attempting a restricted action as each role and confirming correct allow/deny
- A2: Every login, role change, and settings change produces an audit log row with correct actor/timestamp
- A3: Dashboard loads and displays current spend and active-collection count without manual data entry

### Phase 2 — LangGraph pipeline migration (parallel to Phase 1/3)
**Scope:** Vision doc §3 nodes 1-11 implemented as a LangGraph StateGraph with Postgres checkpointer; parallel run against real Trend Scout briefs; publish step untouched initially.
**Acceptance criteria:**
- A4: A sample of briefs run through the new graph produce output equivalent to the current Paperclip/Hermes pipeline (same brief → same collection-cluster/design-spec shape)
- A5: Checkpointer state for a full run is inspectable and matches the design record schema (Data/API spec §1.3)
- A6: No node silently uses the wrong model (the current single-model-override bug) — verified by checking actual model IDs used per node against the routing table (Data/API spec §3)

### Phase 3 — Approvals + Collections screens (depends on Phase 1 + partial Phase 2)
**Scope:** Collections list/detail/create/approve, aggregated Approvals queue, HITL `interrupt()`/`Command(resume=...)` wiring for the collection-contract gate specifically (first gate to wire, since it's the highest-leverage one per Vision doc §2).
**Acceptance criteria:**
- A7: A clustered Trend Scout brief set appears as a candidate collection in the Approvals queue and can be approved/rejected from the Control Panel alone, with no manual file/API intervention required (PRD NFR-2)
- A8: Approving a candidate produces a valid collection contract YAML matching the schema (Data/API spec §1.1) and is reflected in the Collections list immediately
- A9: Retiring a collection with a survivor-product exception correctly keeps that product live and flagged, verified against a test case

### Phase 4 — Design QC gate + rubric (depends on Phase 2, Phase 3 patterns reused)
**Scope:** Aesthetic QC node implemented and calibrated (Vision doc §6) against the known ninja-shirt/rocket-design pair plus new held-out test designs; Design QC review screen wired to the same HITL pattern as Phase 3.
**Acceptance criteria:**
- A10: The rubric scores the known negative example (mixed-style "ninja" design) below the pass threshold and the known positive example (rocket design) above it, without hand-tuning specifically to force that result
- A11: Human reviewer decisions and rubric verdicts are logged side-by-side (UX spec §3.3 calibration indicator) for at least N designs before any consideration of turning this gate's HITL off
- A12: Regeneration-with-feedback loop produces a materially different next render when a design is rejected with a note (not a no-op retry)

### Phase 5 — Fourthwall integration finalization + publish cutover
**Scope:** MCP product-create spike executed and decided (hand-rolled vs. MCP, per Vision doc §4); publish gate wired into Control Panel; full pipeline publish step cut over from the old system to the new LangGraph pipeline.
**Acceptance criteria:**
- A13: The spike produces a documented decision (which mechanism handles product-create) with evidence, not an assumption
- A14: A real product is published end-to-end through the new pipeline, price-invariant check passing automatically, and appears correctly in Fourthwall
- A15: Old Paperclip/Hermes publish path is confirmed inactive (no dual-write risk) before this phase is marked complete

### Phase 6 — Full traceability + catalog mirror + analytics
**Scope:** Pipeline Run detail screen (node-by-node replay), Catalog screen (Fourthwall-sourced read mirror), Analytics dashboards per collection, webhook-driven Analytics trigger replacing polling.
**Acceptance criteria:**
- A16: Any live product's full causal chain (brief → contract → QC scores → approver → publish) is reconstructable from the Control Panel alone (PRD FR-22), tested by picking a real product and tracing it end-to-end
- A17: A Fourthwall order webhook correctly triggers an Analytics run and updates the relevant collection's KPI status without manual polling
- A18: Replay-from-node correctly resumes a run using only its recorded upstream state, verified by replaying a completed run's mid-pipeline node and confirming it doesn't re-execute earlier nodes

### Phase 7 — Graduation review (data-driven, not calendar-driven)
**Scope:** Review calibration data from Phase 4 (A11) and publish-gate history; decide, with evidence, whether to move any HITL gate's default to Off (Vision doc §6.4).
**Acceptance criteria:**
- A19: A documented decision exists for each HITL gate (kept on / turned off) with the supporting data referenced, not a unilateral toggle flip

## 3. Cross-cutting acceptance criteria (apply across all phases)

- CC-1: No phase introduces a second source of truth for pipeline state (Technical Spec §6) — verified by confirming the Control Panel always reads through the checkpointer/contract files, never a cached duplicate
- CC-2: No Fourthwall write action is reachable from two different code paths (Control Panel and pipeline both able to create a product independently) — verified by code review at each phase touching Fourthwall
- CC-3: Every HITL toggle change and every approve/reject action produces an audit row, checked as part of each phase's own acceptance testing, not deferred to a final audit pass

## 4. Sign-off checklist (per phase)

- [ ] All acceptance criteria for the phase pass on a real (not synthetic) example
- [ ] No regression in a previously-signed-off phase's acceptance criteria
- [ ] Audit log correctly captures every state-changing action introduced in this phase
- [ ] Founder (Admin) has exercised the phase's UI directly, not just reviewed a demo

## 5. Definition of "done" for v1.0 overall

The system is considered v1.0-complete when: the full pipeline runs on LangGraph with the publish step cut over (Phase 5), the Control Panel is the sole operational interface for approvals/config/traceability (Phases 1-6), and at least one full collection lifecycle (research → approval → design → QC → publish → rotate/retire) has completed with the founder using only the Control Panel — no manual file edits, no direct database queries, no SSH-based intervention.

---

*This closes the document set: Vision (why/how at the system level) → Product Definition (what/who) → PRD (control panel requirements) → UX Spec (screens/interactions) → Technical Spec (architecture) → Data/API/LLM Spec (schemas/contracts) → this document (how it gets built and accepted).*
