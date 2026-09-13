# SWE Drip — Data / API / LLM Specification v1.0

*Concrete schemas and contracts underlying the Technical Specification. This is the reference for implementers — field names, endpoint shapes, and model routing decisions.*

---

## 1. Core data model

### 1.1 Collection contract (YAML file, `/collections/<slug>.yaml`)
```yaml
collection_id: string           # slug, unique
theme: string
status: draft | active | retired
style_archetype: enum           # one of the 7 locked brand styles
illustration_rules:
  line_weight: string
  palette: [string]              # hex or named brand colors
  no_mixed_styles: boolean       # true always, per brand-lock rule
garment_colorways:
  - base: string                 # e.g. black, charcoal, white
    contrast_pass: boolean
placement_templates:
  - design_type: enum             # hero-icon | wordmark | log-block | brand-mark-only
    front: enum                   # none | chest | full
    back: enum
    sleeve: enum
product_count_target: integer
lifecycle_days: integer
kpi_thresholds:
  min_units: integer
  min_conversion: float
  eval_window_days: integer
created_by: user_id
created_at: timestamp
approved_at: timestamp | null
retired_at: timestamp | null
```

### 1.2 Postgres tables (Control Panel + checkpointer)

**`users`**
`id, email, role (admin|operator|viewer), created_at, last_login_at`

**`audit_log`** (append-only)
`id, actor_user_id, timestamp, action, entity_type, entity_id, before_json, after_json`

**`pipeline_runs`** (thin index over LangGraph checkpointer state, for fast listing/filtering)
`id, collection_id, design_id, current_node, status (running|awaiting_approval|failed|complete), started_at, updated_at`

**`hitl_approvals`**
`id, run_id, node, status (pending|approved|rejected|regenerate_requested), reviewer_user_id, note, decided_at`

*(LangGraph's own checkpointer tables hold the full per-node state payloads; these tables are lightweight indexes for UI querying, not a duplicate of that state — per Technical Spec §5.)*

### 1.3 Design record (within pipeline state, not a separate table)
```json
{
  "design_id": "string",
  "collection_id": "string",
  "brief": { "subject": "...", "text": "...", "style": "..." },
  "render": { "file_url": "...", "model_used": "...", "colorways_valid": ["black", "charcoal"] },
  "qc_scores": {
    "style_cohesion": 0-100,
    "focal_point": 0-100,
    "placement_fit": 0-100,
    "contrast": 0-100,
    "pass_threshold": 70,
    "result": "pass | fail"
  },
  "placement": { "front": "chest", "back": "none", "sleeve": "small-mark" }
}
```

## 2. Control Panel API — endpoint summary

*(REST, JSON; all endpoints require an authenticated session; role checks noted where restrictive.)*

| Method | Path | Purpose | Role |
|---|---|---|---|
| GET | `/api/dashboard/summary` | Stat cards: pending approvals, spend vs cap, active collections | Viewer+ |
| GET | `/api/collections` | List collections, filterable by status | Viewer+ |
| GET | `/api/collections/{id}` | Collection detail incl. products, KPI history | Viewer+ |
| POST | `/api/collections` | Create a draft collection contract | Admin |
| PATCH | `/api/collections/{id}` | Edit contract fields | Admin |
| POST | `/api/collections/{id}/approve` | Approve a candidate collection (HITL gate) | Admin, Operator |
| POST | `/api/collections/{id}/retire` | Retire, with optional survivor product exception | Admin |
| GET | `/api/runs` | List pipeline runs, filterable | Viewer+ |
| GET | `/api/runs/{id}` | Full node-by-node state history | Viewer+ |
| POST | `/api/runs/{id}/replay` | Replay from a specified node | Admin, Operator |
| GET | `/api/approvals` | Aggregated pending HITL queue (all types) | Viewer+ (action requires Operator+) |
| POST | `/api/approvals/{id}/decision` | Approve / reject / regenerate, with optional note | Admin, Operator |
| GET | `/api/designs/{id}` | Design detail incl. render, QC scores, placement | Viewer+ |
| GET | `/api/catalog` | Mirrored Fourthwall product list w/ price-invariant status | Viewer+ |
| GET | `/api/catalog/{product_id}` | Product detail incl. order history | Viewer+ |
| GET | `/api/agents` | Agent roster, model routing, budget/spend | Viewer+ |
| PATCH | `/api/agents/{id}/config` | Edit model routing or budget cap | Admin |
| GET | `/api/analytics/collections/{id}` | KPI time series for a collection | Viewer+ |
| GET | `/api/audit` | Filterable audit log | Viewer+ |
| GET | `/api/settings/hitl` | Current HITL toggle state per node | Viewer+ |
| PATCH | `/api/settings/hitl` | Toggle HITL per node (with confirmation) | Admin |
| GET | `/api/users` | List users/roles | Admin |
| POST | `/api/users` | Invite user | Admin |
| PATCH | `/api/users/{id}` | Change role / deactivate | Admin |

**Real-time channel:** `GET /api/stream/runs` (SSE) — pushes run-status and approval-queue deltas to connected clients, backing the Dashboard and Approvals live-update behavior (Technical Spec §2).

## 3. LLM / model routing specification

*Corrects and finalizes the model-routing ambiguity found in the current implementation audit (SOUL files declare varied models; live Hermes gateway execution currently overrides all of them to a single DeepSeek model). Going forward, on LangGraph, each node calls its intended model directly — no gateway override layer to cause this divergence.*

| Pipeline node | Model | Purpose |
|---|---|---|
| Trend research + clustering | `google/gemini-2.0-flash-001` (or current equivalent low-cost fast model) | Scoring rubric, cheap and frequent |
| Collection contract drafting | `anthropic/claude-sonnet-4-6`-class model | Higher-judgment synthesis of clustered briefs |
| Listing copy | `anthropic/claude-sonnet-4-6`-class model | Brand-voice copywriting |
| Design spec | `anthropic/claude-sonnet-4-6`-class model | Creative-direction reasoning (RCAO framework) |
| Art render | `riverflow-v2-pro` (primary), `gpt-5-image-mini` / `seedream` (fallback) | Native transparent-alpha image generation |
| Aesthetic QC | vision-capable model (e.g. a Claude or Gemini multimodal variant) | Rubric scoring against rendered image |
| Analytics / KPI summary | `anthropic/claude-haiku-4-5`-class model | Cheap, frequent, low-judgment reporting |
| Finance reconciliation | `google/gemini-2.0-flash-001`-class model | Structured numeric reconciliation |

All model calls route through OpenRouter directly (single key, as already configured), with **per-node** model IDs in code/config — not a shared gateway payload template that can silently override every node to one model, which is the exact bug identified in the current Paperclip/Hermes implementation.

**Cost tracking:** every model call logs `{node, model, tokens_in, tokens_out, cost_usd}` to the audit trail (or a dedicated cost table), rolled up into the Dashboard's spend-vs-cap figure (PRD FR-2) and per-agent spend view (PRD FR-17) — replacing the current unreliable "Observed spend field: 0" gap noted in the implementation audit, where Hermes gateway usage wasn't priced inside Paperclip at all.

## 4. Fourthwall integration contract

| Operation | Mechanism | Notes |
|---|---|---|
| Read orders/analytics | Fourthwall MCP server (OAuth2) | Scheduled pulls for dashboard/KPI data |
| Product creation | MCP write tool **if** parameter coverage matches placement matrix (spike required, Vision doc §4); else hand-rolled Open API (signed URL flow) | Decision made per-spike-result, not assumed |
| Order/checkout events | Fourthwall webhook → dedicated Control Panel API endpoint → triggers Analytics pipeline run | Replaces heartbeat/cron polling |
| Price invariants | Enforced at pipeline Shelf node before any Fourthwall write call | Never a post-hoc catalog correction |

---

*See: Delivery/Acceptance Specification for phasing this schema/API surface into buildable increments with sign-off criteria.*
