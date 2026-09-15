# SWE Drip — Product Vision Document v1.0
**An autonomous design studio, print-on-demand operation, storefront, and marketing engine for software-engineer culture merchandise**

*Status: decisions locked from v0.1 framework review. This is the reference document for the v2 build — the LangGraph state schema, collection contract schema, and QC rubric all derive from this.*

---

## 1. Vision statement

SWE Drip runs as close to end-to-end autonomously as the current agentic tooling allows: trend research, collection strategy, design generation, quality gating, product publishing, pricing, and marketing all execute as a single orchestrated pipeline with human oversight concentrated at the few points where judgment genuinely matters — not scattered across every step by default, and not absent from any step that carries real consequence.

The brand identity (terminal/dev culture, dry self-aware humor, monochrome-first aesthetic) is a fixed creative constraint the system operates inside, not something it reinvents per product. Collections — not individual designs — are the unit of creative strategy; individual designs are largely mechanical once a collection contract is locked.

## 2. What "full circle" means here

Research → Collection strategy → Design → QC → Publish → Price → Market → Measure → Rotate. The system is judged as a loop, not a pipeline with an end: Analytics feeding back into collection retirement/rotation is as much a part of the product as the initial design generation is.

## 3. System architecture

### 3.1 Orchestration substrate: LangGraph
The 9-step (soon 11-step, with QC and placement-resolver nodes added) product pipeline is rebuilt as a LangGraph `StateGraph` with a Postgres checkpointer — reusing existing Postgres/pgvector infrastructure rather than adding a new persistence system. Paperclip/Hermes is retired from the core product pipeline once migration is validated; it may continue to serve genuinely reactive, non-DAG-shaped work (e.g. Community Agent's monitor-and-reply loop) if that turns out not to benefit from being forced into graph form — that is a separate, later evaluation, not part of this migration.

**Migration sequencing:** build the new graph, run it in parallel against real Trend Scout briefs without touching the Fourthwall publish step, verify output parity against the current pipeline, then cut over the publish step last (highest blast radius, given two products — EXIT 0, UNTIL USER 50 — are already live and selling).

### 3.2 Pipeline (locked node list)

| # | Node | Type | HITL |
|---|---|---|---|
| 1 | Trend research + clustering | Deterministic scoring (engagement/novelty/specificity ≥60) + thematic clustering into collection candidates | Off |
| 2 | Collection contract approval | CEO reviews clustered brief set, approves as a locked collection contract (style, palette, colorways, placement templates, KPI thresholds) | **On** |
| 3 | Listing copy | Slogan/title/description/tags generation | Off |
| 4 | Design spec | Per-design brief resolved against the active collection contract (style/palette/placement inherited, not re-decided) | Off |
| 5 | Art render | Image generation against the resolved spec | Off |
| 6 | Placement & colorway resolution | Deterministic function of (collection contract, design type) → placement zones + contrast-valid colorways | Off |
| 7 | Aesthetic QC | Vision-model rubric: style-cohesion, single-focal-point, placement-fit, contrast-per-colorway; conditional edge — pass continues, fail regenerates (prompt + rubric feedback, capped retries), exhausted retries fall to human review | **On** (until calibrated against enough real pass/fail history — see §5) |
| 8 | Technical QC | RGBA/dimension/transparency validation (unchanged from current implementation) | Off |
| 9 | Fourthwall product create | Hybrid: official Fourthwall MCP product-creation tool where its parameter coverage matches the placement matrix; hand-rolled Open API calls where it doesn't (see §4) | — |
| 10 | Publish gate | Final review before `state: PUBLIC` | **On** |
| 11 | Shelf (pricing/collection assignment) | Price-invariant check ($32 tee / $62 hoodie / $20 mug), collection assignment | Off |

Every node — including the "Off" ones — is implemented with `interrupt()` capability from the start. The HITL default is a config flag on the node/collection contract, not a structural difference in the graph. This means toggling HITL for design validation on or off is a config change, never a rebuild.

### 3.3 State and memory

- **Execution state / replay / audit:** LangGraph Postgres checkpointer. Every design's full brief→spec→render→QC history is queryable and replayable.
- **Strategic/institutional memory:** stays in `program.md` / `program-summary.md` as human-(and CEO-agent-)readable prose — kill rules, pricing invariants, performance log. This is not migrated into structured state; it's read holistically by design.
- **Collection contracts:** `/collections/<slug>.yaml` — the single source of truth for style, palette, colorways, placement templates, and KPI thresholds. Both the generation nodes and the rotation/retirement decision read the same file, so they cannot drift out of sync with each other.

### 3.4 Trigger model

Heartbeat polling and issue-checkout-as-wake are retired for the core pipeline. Replaced with:
- **Scheduled jobs** for cadence-driven work (monthly collection rotation, weekly Trend Scout runs)
- **Fourthwall webhooks** (order/checkout events) for reactive work (Analytics' scale/kill re-evaluation)
- **Direct invocation** for anything explicitly CEO-gated

### 3.5 Observability
Read the checkpointer directly for status/debugging (reusing existing Postgres access patterns). LangSmith is adopted only if debugging friction becomes a measurable time cost — not stood up preemptively.

## 4. Fourthwall integration strategy

**Hybrid, decided as follows:**
- **Reads (orders, analytics, KPI pulls for the Analytics Agent):** Fourthwall Platform Open API (`https://api.fourthwall.com/open-api/v1.0/*`) with a shop-level Open API user (HTTP Basic), configured server-side — see ADR-005. The official MCP server (`mcp.fourthwall.com`) is OAuth-2.0-interactive-only and cannot accept a configured static credential, so it is deferred for reads; its report tools remain available if a later PBI adds an MCP OAuth connect flow.
- **Product creation:** spike the MCP server's artwork-to-product write tool against the placement matrix (front/back/sleeve, multi-region) before committing. If its parameter coverage matches what the placement matrix needs, retire the hand-rolled signed-URL flow (current steps 6-8) entirely — real code deletion. If it's coarser (e.g. can't address multi-region placement), keep the hand-rolled flow for product-create specifically while still using MCP for everything else.
- **Shop provisioning / multi-shop concerns:** out of scope for SWE Drip specifically (Channel API is invite-only beta, relevant only if SWE Drip becomes a platform for other creators' shops — not the current goal).

## 5. Collection system

Collections are the unit of creative strategy; a locked contract inherits down to every design generated under it, eliminating per-design creative re-litigation.

- **Authorship:** Trend Scout's existing scored briefs are grouped by thematic similarity; a cluster of 3-4 passing briefs is a collection candidate. CEO approves the cluster as a collection using the same GO/NO-GO contract shape already in use for individual briefs, applied one level up. No new agent role.
- **Contract schema** (locked shape, from prior draft): `theme`, `style_archetype` (one of the 7 brand styles), `illustration_rules` (line weight, palette, no-mixed-styles flag), `garment_colorways` (each tagged `contrast_pass: true/false`), `placement_templates` (keyed by design type — hero-icon, wordmark, log-block, brand-mark-only), `product_count_target`, `lifecycle_days`, `kpi_thresholds`.
- **Rotation:** Analytics Agent evaluates each collection against its own `kpi_thresholds` at `eval_window_days`. Below threshold → CEO gets a retire recommendation (inverse of the GO/NO-GO contract). Retirement is per-collection, not per-product — a strong individual seller survives even if its collection average underperforms. A new collection contract should already be queued from the standing backlog of scored briefs so rotation never stalls waiting on fresh research.

## 6. Design quality policy

The core problem this whole system exists to solve for the founder — "I struggle to produce good-looking t-shirts" — is addressed structurally, not by hoping the model tries harder:

1. **Style-lock at the collection level** prevents the failure mode already observed in production (a design mixing pixel-art, flat-icon, and cartoon elements in one composition — the "ninja shirt" case) before generation even happens.
2. **Placement-by-design-type** (§3.2 node 6) removes ad hoc placement decisions — a log-block design is never asked to fit a hero-icon's front-chest slot.
3. **Aesthetic QC rubric** (node 7) is the automated backstop, scored on style-cohesion, single-focal-point, placement-fit, and contrast-per-colorway — the same four criteria used to diagnose the ninja-shirt failure and the rocket-design success in live testing.
4. **HITL stays on at this gate** until the rubric has been run against enough real designs — with real sales/return outcomes as ground truth — to trust its verdict unsupervised. This is a data-driven graduation, not a timeline-driven one.

## 7. Roadmap

| Phase | Scope | Exit criterion |
|---|---|---|
| v0.2 | LangGraph state schema + node implementations for steps 1-11; parallel run against live Trend Scout briefs, publish step untouched | Output parity with current Paperclip/Hermes pipeline on a sample of briefs |
| v0.3 | Fourthwall MCP product-create spike; collection contract schema implemented as YAML + resolver skill | Decision made on hand-rolled-vs-MCP for product-create, with evidence |
| v0.4 | Aesthetic QC rubric implemented and calibrated against ninja-shirt/rocket-design pair plus new test designs; HITL still on | Rubric agrees with human judgment on a held-out design set above an agreed threshold |
| v0.5 | Cut over Fourthwall publish step to new pipeline; retire Paperclip/Hermes for core pipeline | First new product published entirely through the LangGraph pipeline |
| v1.0 | HITL graduated to Off on aesthetic QC (data-justified); full monthly collection rotation running unattended; webhook-driven Analytics reactivity live | One full collection lifecycle (research → publish → rotate) completes without a founder intervention beyond the remaining locked HITL gates (collection approval, final publish) |

## 8. Success metrics

- **Design quality (leading indicator):** aesthetic-QC pass rate on first render attempt (fewer regenerations = better-calibrated collection contracts and prompts)
- **Design quality (lagging indicator):** return/complaint rate per collection, correlated against QC scores to validate the rubric itself
- **Operational:** monthly AI spend vs. $130 cap; break-even at 4-5 shirt sales (unchanged baseline)
- **Commercial:** units and conversion per collection against each contract's own `kpi_thresholds`; time from collection approval to first live product; storefront moving off `COMING_SOON`

## 9. Explicit non-goals (for this version)

- Multi-creator/platform ambitions (Fourthwall Channel API) — not in scope
- Showcase/lifestyle-scene generation — disabled per founder decision, pipeline ends at rendered mockups
- Full removal of Paperclip/Hermes from every workflow — only the core product pipeline migrates; reactive/conversational agents are evaluated separately, later

---

*This document supersedes the v0.1 decision framework. Next artifacts: LangGraph state schema + node code skeletons (§3.2), collection contract YAML template + resolver skill (§5), aesthetic QC rubric spec (§6).*
