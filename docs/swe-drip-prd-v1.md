# SWE Drip — Product Requirements Document (PRD) v1.0

*Scope note, superseding one assumption in the earlier Product Definition doc: SWE Drip does not build or own a storefront. Fourthwall is the storefront system of record end-to-end (catalog, cart, checkout, payments). The product surface this org builds and owns is the **Control Panel** — an internal, multi-user, secure dashboard for operating and configuring the design/production pipeline. This PRD covers the Control Panel only; storefront behavior is Fourthwall's product, referenced here only where the Control Panel reads from or writes to it.*

---

## 1. Purpose

Give the founder (and, as the operation grows, additional operators) a single place to: see what the autonomous pipeline is doing right now, approve or reject the handful of HITL-gated decisions, configure collections and pipeline behavior without touching code, and reconstruct — after the fact — exactly why any product, price, or publish decision happened.

## 2. Users and roles

| Role | Who | Permissions |
|---|---|---|
| **Admin** | Founder | Full access: configure HITL toggles, edit collection contracts, manage users, view/edit agent config and budgets, approve/reject at any gate |
| **Operator** | A future hire/collaborator handling day-to-day approvals | Approve/reject at HITL gates, view all dashboards/audit log, cannot change agent config, budgets, or user management |
| **Viewer** | Anyone needing visibility without action rights (e.g. a future co-founder, accountant) | Read-only across all dashboards and audit log; no approve/reject, no config |

Multi-user, role-based access is a **launch requirement**, not a v2 add-on — the traceability and approval features are meaningless if any single session can silently act as any role.

## 3. Functional requirements

### 3.1 Dashboard / Overview
- FR-1: Show current pipeline health at a glance: active runs, runs awaiting HITL approval, runs failed/retrying
- FR-2: Show monthly AI spend vs. the $130 cap, updated per run, with a visible warning state above 80%
- FR-3: Show a snapshot of active collections and their KPI status (on-track / at-risk / below-threshold)

### 3.2 Collections management
- FR-4: List all collection contracts (active, retired, draft) with their key fields (style, colorways, lifecycle window, KPI thresholds)
- FR-5: Create/edit a collection contract through a form (not raw YAML editing) that maps to the schema in the Data/API spec — the underlying file is still YAML, the Control Panel is the authoring surface
- FR-6: Surface CEO's clustered Trend Scout brief groups as collection *candidates* awaiting approval — this is the collection-contract HITL gate from the Vision doc, realized as a UI action (approve / reject / edit-and-approve)
- FR-7: Show retirement recommendations (from Analytics, per KPI thresholds) with an approve/override action; support the "individual survivor" exception (keep one product live even if its collection is retired)

### 3.3 Pipeline / graph operations
- FR-8: List pipeline runs (per design, per collection cycle) with current node, status, and timestamp history
- FR-9: Inspect a specific run's full state history (brief → spec → render → QC → publish) — this is the LangGraph checkpointer surfaced as a UI, not a new data source
- FR-10: Replay or re-trigger a run from a specific node (e.g. re-render after a QC failure) without re-running the whole pipeline from scratch
- FR-11: A pending-approvals queue aggregating every open HITL gate across collections/designs/publishes, actionable from one list

### 3.4 Design QC review (HITL gate realized in UI)
- FR-12: Side-by-side view: rendered design, the four rubric scores (style-cohesion, focal-point, placement-fit, contrast-per-colorway), and the pass/fail threshold
- FR-13: Approve / reject / request-regeneration actions, with an optional free-text note that feeds back into the next regeneration prompt
- FR-14: A running calibration view — designs and their human-vs-rubric agreement, to make the "graduate this gate to unsupervised" decision (Vision doc §6) with actual evidence, not a guess

### 3.5 Products & catalog (read-mostly, Fourthwall-sourced)
- FR-15: Mirror published products (via Fourthwall MCP/API reads) with price-invariant status (pass/fail against $32/$62/$20)
- FR-16: Surface Fourthwall order/sales events relevant to Analytics' scale/kill/rotation logic — the Control Panel does not process payments or manage cart/checkout; it only reads outcomes

### 3.6 Agents & configuration
- FR-17: View each agent's role, current model routing, monthly budget cap and spend-to-date
- FR-18: Toggle HITL on/off per pipeline node (the config flag described in the Vision doc), with a confirmation step given the consequence of turning off a gate
- FR-19: View/edit brand-lock constants (palette, fonts, forbidden style elements) that generation nodes read

### 3.7 Traceability / audit
- FR-20: Every state-changing action (contract approval, HITL decision, config change, user/role change) is logged with actor, timestamp, before/after values
- FR-21: Audit log is filterable (by collection, by user, by date range, by action type) and exportable
- FR-22: Any live product's full causal chain — which brief, which contract, which QC scores, which approver — must be reconstructable from the audit log alone, without needing to cross-reference multiple systems by hand

### 3.8 Users & access
- FR-23: Admin can invite/remove users and assign roles
- FR-24: Session security appropriate to a financially-consequential internal tool (see Technical Spec for auth mechanism)

## 4. Non-functional requirements

- NFR-1: Control Panel must not become a second source of truth for pipeline state — it reads/writes through the same LangGraph checkpointer and collection-contract files the pipeline itself uses, never a parallel copy
- NFR-2: All HITL actions must be possible from the Control Panel alone — no requirement to SSH into infra or hand-edit a YAML file to approve or reject a gate
- NFR-3: Visual identity: shadcn/ui component kit, dark/black theme consistent with the SWE Drip brand lock (void black, terminal green accents), not a generic admin-template look
- NFR-4: Must run on existing infra (Coolify/Hetzner) alongside the rest of the stack — no new hosting provider

## 5. Out of scope (explicit)

- Storefront UI of any kind — Fourthwall owns this fully
- Payment processing UI — Fourthwall is merchant of record
- Customer-facing anything — the Control Panel is 100% internal
- Mobile app — responsive web is sufficient for an internal ops tool at this scale

---

*See: UX Specification (screen-level detail, IA, shadcn design system application), Technical Specification (architecture/auth/hosting), Data/API/LLM Specification (schemas, endpoints, model routing), Delivery/Acceptance Specification (phasing and sign-off criteria).*
