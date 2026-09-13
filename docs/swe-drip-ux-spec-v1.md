# SWE Drip — UX Specification v1.0
**Control Panel — information architecture, screens, and design system**

*This document specifies the experience of the Control Panel only (no storefront — see PRD §scope). Every screen here maps to functional requirements in the PRD; this document adds layout, interaction, and visual-system detail.*

---

## 1. Design principles

1. **Operational clarity over decoration.** This is a founder checking "what needs my attention right now" multiple times a day — the dashboard's first screen must answer that in under 5 seconds of scanning, not require navigation.
2. **Approval actions are never buried.** Every HITL gate (collection, design QC, publish) surfaces in one aggregated queue, in addition to living inside its own context (a design's detail page also shows its pending approval).
3. **Traceability is a first-class view, not a debug afterthought.** The audit log/run-history views are designed with the same care as the dashboard — this is the tool's actual differentiator over "just check the database."
4. **Dark, technical, terminal-adjacent — but a real product UI, not a terminal emulator.** Brand-consistent (void black, terminal green) without literally mimicking a CLI; this is a dashboard for humans making decisions, not a log tail.

## 2. Information architecture

```
Control Panel
├─ Dashboard (home)
├─ Collections
│   ├─ Active
│   ├─ Candidates (pending approval)
│   ├─ Retired
│   └─ [Collection detail] → contract fields, products in it, KPI chart, retire/edit actions
├─ Pipeline Runs
│   ├─ All runs (filterable by collection/status/date)
│   └─ [Run detail] → node-by-node state history, replay-from-node action
├─ Approvals (aggregated HITL queue)
│   ├─ Collection contracts awaiting approval
│   ├─ Designs awaiting QC review
│   └─ Products awaiting publish approval
├─ Design QC
│   ├─ Queue (same items as Approvals→Designs, deep-linked)
│   └─ [Design detail] → render + rubric scores + approve/reject/regenerate
├─ Catalog (read-mostly, Fourthwall-sourced)
│   └─ [Product detail] → price-invariant status, order history, collection membership
├─ Agents
│   └─ [Agent detail] → role, model routing, budget/spend, recent runs
├─ Analytics
│   └─ Per-collection KPI dashboards, overall revenue vs. break-even line
├─ Audit Log
│   └─ Filterable event stream, exportable
└─ Settings
    ├─ HITL toggles (per pipeline node)
    ├─ Brand-lock constants
    ├─ Users & Roles
    └─ Integrations (Fourthwall MCP connection status, OpenRouter key status)
```

## 3. Key screens

### 3.1 Dashboard (home)
- Top row: three stat cards — *Runs awaiting approval* (count, links to Approvals), *Monthly spend* (progress bar vs. $130 cap, amber above 80%), *Active collections* (count + at-risk flag if any KPI is below threshold)
- Middle: activity feed — last N pipeline events (design rendered, QC passed/failed, product published, collection retired) with relative timestamps
- Right rail (desktop) / below (mobile): pending-approval list, top 3-5 items, "View all" to Approvals

### 3.2 Approvals (the single most important screen)
- Tabbed by type (Collections / Designs / Publishes) but a combined "All" default view
- Each row: what it is, which collection, how long it's been waiting, one-click approve, one-click reject-with-note, link to full detail
- This screen exists precisely because HITL gates are scattered across three different pipeline stages (Vision doc §3.2) — the UI's job is to make that scattering invisible to the person approving

### 3.3 Design QC detail
- Large render preview (the actual design image) with garment-color swatches showing valid colorways (from placement/colorway resolution) next to invalid ones (greyed out, with the contrast-fail reason on hover)
- Four rubric scores as a compact horizontal bar set (style-cohesion, focal-point, placement-fit, contrast), each with the pass threshold marked
- Actions: Approve → continues pipeline; Reject → requires a note (feeds the regeneration prompt per FR-13); Regenerate directly with edited note
- A small "calibration" indicator showing how this design's human decision compares to what the rubric alone would have decided — this is the data trail that eventually justifies turning this gate's HITL off (Vision doc §6.4)

### 3.4 Collection detail
- Header: theme, style archetype, status (active/candidate/retired), lifecycle countdown
- Contract fields shown as a readable form, not raw YAML (palette swatches rendered as actual color chips, placement templates shown as small diagrams per design-type, not a table of enum strings)
- Products-in-this-collection grid with live sales figures per product
- KPI chart: units/conversion over time against the contract's own thresholds, with the retirement-recommendation banner if Analytics has flagged it

### 3.5 Pipeline run detail (traceability core)
- Horizontal step tracker matching the locked node list (Vision doc §3.2): Trend → Contract → Copy → Spec → Render → Placement → Aesthetic QC → Technical QC → FW Create → Publish Gate → Shelf
- Each node clickable to expand its recorded state at that point (the checkpointer's stored state for that node)
- "Replay from here" action on any node — re-triggers the pipeline starting at that node using its recorded upstream state, without re-running everything before it

### 3.6 Audit log
- Single filterable table: timestamp, actor, action, entity (collection/design/product/user), before → after diff where applicable
- Every row here should be sufficient, on its own, to answer "why did this happen" without needing the run-detail screen — the two views are cross-linked but each independently useful

## 4. Interaction patterns

- **Approve/reject is always two clicks maximum** from any list view — no forced navigation into a detail screen just to approve something the summary already shows enough to judge (though the detail screen remains available for anything ambiguous)
- **Optimistic UI with visible pending state** for approval actions, since they trigger real backend pipeline resumption (LangGraph `Command(resume=...)`) — the UI should show "resuming pipeline…" rather than pretend the action completed instantly
- **No destructive action without confirmation** — retiring a collection, turning off a HITL gate, and removing a user all require a confirm step, matching PRD NFR requirements around HITL toggle changes

## 5. Design system

- **Component kit:** shadcn/ui (matches existing stack conventions), black/dark theme as the only theme — no light-mode toggle needed for an internal tool with a fixed brand identity
- **Palette:** void black `#0D0D0D` background, terminal green `#00FF41` as the single accent (used sparingly — primary actions, active states, success indicators), neutral grays for secondary text/borders, amber/red reserved strictly for warning/danger states (budget approaching cap, QC failure, retirement recommendation)
- **Typography:** JetBrains Mono for data/numeric/code-adjacent content (run IDs, model names, timestamps, rubric scores) to reinforce the brand's technical identity; a standard humanist sans (e.g. Inter) for prose/labels so the whole UI doesn't read as a terminal emulator
- **No gradients, shadows, rounded pills, or pastels** — same constraint already enforced on the storefront brand CSS, carried into the Control Panel for internal brand consistency
- **Density:** this is a power-user tool used daily, not a marketing surface — favor compact table/list density over generous whitespace, especially in Approvals and Audit Log

## 6. Accessibility and responsiveness

- Desktop-first (this is an ops tool, primary usage is at a desk), but all screens must degrade gracefully to a single-column layout on tablet/mobile for the founder to approve/reject from a phone
- Standard contrast-ratio compliance even within the dark theme — terminal green on void black must be checked against WCAG AA for body text use, restricting green to accents/icons/short labels rather than long-form text if contrast testing shows an issue

---

*See: PRD (functional requirements this screen set satisfies), Technical Specification (frontend stack, real-time update mechanism for run status), Data/API/LLM Specification (exact fields rendered in each screen).*
