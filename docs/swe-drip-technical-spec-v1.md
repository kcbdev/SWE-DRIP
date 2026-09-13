# SWE Drip — Technical Specification v1.0

*Covers the Control Panel application and its integration surface with the LangGraph pipeline. Does not re-specify the pipeline's internal node logic (see Vision doc §3) or storefront behavior (owned entirely by Fourthwall).*

---

## 1. System components

```
┌─────────────────────────────────────────────────────────────┐
│  Control Panel (Next.js 15 + shadcn/ui)                     │
│  - Dashboard, Collections, Approvals, QC, Catalog,           │
│    Agents, Analytics, Audit, Settings                        │
└───────────────┬───────────────────────────────┬─────────────┘
                │ REST/GraphQL (auth'd)          │ SSE/WebSocket (live run status)
                ▼                                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Control Panel API (FastAPI / Python)                        │
│  - Auth (multi-user, RBAC)                                   │
│  - Read/write to LangGraph checkpointer                      │
│  - Read/write collection contract files                      │
│  - Audit log writer (every state-changing call)               │
│  - Fourthwall MCP client (reads: orders, analytics)           │
└───────┬─────────────────────┬─────────────────┬──────────────┘
        │                     │                 │
        ▼                     ▼                 ▼
┌───────────────┐   ┌──────────────────┐  ┌─────────────────┐
│ Postgres       │   │ LangGraph engine  │  │ Fourthwall MCP  │
│ (checkpointer  │   │ (pipeline nodes,  │  │ server (reads)  │
│  + audit log + │   │  interrupt/resume)│  │ + hand-rolled   │
│  users/roles)  │   │                    │  │ API (writes,    │
│                │   │                    │  │ per Vision §4)  │
└───────────────┘   └──────────────────┘  └─────────────────┘
```

## 2. Frontend

- **Framework:** Next.js 15 (App Router), consistent with existing project conventions
- **UI kit:** shadcn/ui, black theme only (per UX Spec §5) — Tailwind-based, so brand tokens (void black, terminal green, JetBrains Mono) are defined once as CSS variables/Tailwind theme extensions and consumed throughout
- **Real-time updates:** Server-Sent Events (or WebSocket if bidirectional push is needed for multi-user concurrent approval scenarios — e.g. two operators viewing the same Approvals queue must see it update when either acts) for run-status and approval-queue changes, so the Dashboard and Approvals screens don't rely on polling
- **State management:** server-state via React Query (or equivalent) against the Control Panel API; no client-side duplication of pipeline state — the API is the only source read from (NFR-1 in PRD)

## 3. Backend / Control Panel API

- **Framework:** FastAPI (Python), consistent with existing stack
- **Responsibilities:**
  - Expose REST endpoints for every screen in the UX Spec (detailed in the Data/API/LLM Specification document)
  - Translate approval actions (approve/reject/regenerate) into LangGraph `Command(resume=...)` calls against the paused graph run
  - Write every state-changing action to the audit log table before or atomically with performing it — no action should succeed without a corresponding audit row
  - Own the collection-contract YAML files as its storage layer for Collections screens (read for display, write on create/edit, never bypassed by a manual file edit going undetected — audit log should flag file-mtime mismatches if this ever happens)
  - Call the Fourthwall MCP server for reads (orders, analytics) and, pending the spike outcome from Vision doc §4, either the same MCP server or the hand-rolled API for product-create actions triggered from the pipeline (not directly from the Control Panel — the Control Panel triggers/reviews, the pipeline executes)

## 4. Authentication and authorization

- **Auth mechanism:** session-based auth with a dedicated auth secret (mirrors the `BETTER_AUTH_SECRET` pattern already used for Paperclip — reuse the same approach/library for consistency across the founder's stack rather than introducing a second auth paradigm)
- **RBAC:** three roles (Admin, Operator, Viewer per PRD §2) enforced at the API layer, not just hidden in the UI — every endpoint checks role before executing, since a Viewer hitting an approval endpoint directly must be rejected server-side regardless of what the frontend shows
- **Session security:** short-lived sessions with refresh, given this tool can trigger real financial/publish consequences (approving a product publish is not a low-stakes action)
- **Audit binding:** every session is tied to a user identity that's recorded on every audit log row — "who did this" must never be ambiguous

## 5. Data persistence

- **Postgres** (existing pgvector-capable instance, reused — no new database engine introduced):
  - LangGraph checkpointer tables (state per run, per node, replayable)
  - Audit log table (actor, timestamp, action, entity, before/after)
  - Users/roles table
  - Collection contracts remain YAML files (per Vision doc §3.3) referenced by path/slug from Postgres rows — Postgres does not duplicate contract content, it indexes and versions it

## 6. Integration: LangGraph pipeline

- The Control Panel API and the LangGraph pipeline share the same Postgres checkpointer instance — the Control Panel is a *viewer and controller* of pipeline state, not a separate system that mirrors it (PRD NFR-1)
- HITL gates (collection approval, design QC, publish gate) are implemented as `interrupt()` calls in the graph; the Control Panel API's approve/reject/regenerate actions map directly to `Command(resume=...)` invocations — there is no custom approval-queue data model divorced from LangGraph's own interrupt state
- Replay-from-node (UX Spec §3.5) uses the checkpointer's ability to resume execution from a specific stored state, not a custom re-run mechanism

## 7. Integration: Fourthwall

- **Reads** (orders, analytics, product status): Fourthwall MCP server, OAuth2-authenticated, called from the Control Panel API on a schedule (for dashboard/analytics data) and on-demand (for a specific product/order lookup from the UI)
- **Writes** (product creation): owned by the pipeline (LangGraph's FW-create node), not the Control Panel directly — the Control Panel triggers pipeline runs and reviews their outcomes, it does not independently call Fourthwall write endpoints, to avoid two systems being able to create products through different paths
- **Webhooks:** Fourthwall order/checkout webhooks land on a dedicated endpoint that feeds the Analytics pipeline trigger (Vision doc §3.4) — the Control Panel surfaces the resulting KPI changes, it doesn't own webhook receipt logic itself (that belongs to the pipeline's trigger layer)

## 8. Hosting and deployment

- Deployed on existing Coolify/Hetzner infrastructure alongside Paperclip/Hermes (during migration) and eventually alongside the LangGraph service, once that migration completes (Vision doc §3.1 phasing)
- No new hosting provider or platform introduced — this is an additional Coolify-managed service, following the same deployment pattern (Dockerfile-based build, environment/secret management via Coolify) as the rest of the stack

## 9. Observability

- Control Panel itself needs standard application logging/error tracking (not specified in depth here — reuse whatever pattern the founder already applies to other Next.js/FastAPI services)
- Pipeline observability (run status, node-level state) is *not* duplicated in a separate logging system — it's read live from the LangGraph checkpointer, per §6, keeping one source of truth for "what happened in a run"

## 10. Security considerations

- Multi-user + RBAC is a hard requirement given financially consequential actions (publish approval, budget/config changes) — see §4
- Audit log is append-only at the database level (no update/delete permitted on audit rows through the application layer) to preserve the traceability guarantee from PRD §3.7
- Fourthwall and OpenRouter credentials remain server-side secrets (Control Panel API only), never exposed to the frontend — the frontend never holds a Fourthwall or OpenRouter key

---

*See: Data/API/LLM Specification (endpoint list, schemas, model routing table), Delivery/Acceptance Specification (build phasing, test/sign-off criteria).*
