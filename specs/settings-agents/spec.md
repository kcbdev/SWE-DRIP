# Spec: Settings & Agents

## Goal

Make the Control Panel the sole operational interface for configuration (PRD FR-17/18/19, NFR-2): HITL toggles per pipeline node, brand-lock constants, integrations status, and the agent roster with model routing/budget visibility — all reading and writing one config source the pipeline itself consumes.

## Scope

- In scope: settings store + API; HITL toggle screen (confirmation required); brand-lock constants view (founder-gated edit); integrations status (connection/configured state only); Agents screen (roster, routing, budget/spend; Admin edits).
- Out of scope: credential entry (env-managed via Coolify), the cost ledger itself (dashboard/pipeline), agent runtime logic (pipeline nodes), budget enforcement engine.

## Contracts (success criteria)

- **C1 — HITL toggles (FR-18)**: per-node on/off state lives in one settings source that the pipeline reads at run start; flipping a gate requires a confirmation step and writes an audit row; toggling is config-only — never a structural rebuild (pipeline-core C2).
- **C2 — Brand-lock constants (FR-19)**: palette, typeface, and forbidden elements are readable in the UI; edits require Admin + confirmation and are audit-versioned; generation nodes read the same source — no duplicated constants anywhere.
- **C3 — Integrations status**: Fourthwall MCP connection state and OpenRouter key presence (configured/not configured) are surfaced read-only — presence only, never secret values.
- **C4 — Agents (FR-17)**: roster shows each node's role, model routing (from the single routing table), monthly budget cap and spend-to-date; Admin edits to budget caps are explicit, audit-logged, and carry a cost-impact note; model routing is **view-only in v1** — routing changes are reviewed code changes to `pipeline/routing.py` (pipeline-core C3 forbids runtime override layers; the POC's gateway override is the known root-cause bug).
- **C5 — Single config source**: the pipeline consumes the same settings store the UI writes (no parallel constants; NFR-1).
- **C6 — RBAC**: Viewer+ read; Admin write; enforced server-side.

## Anti-patterns

- Constants duplicated between code and UI (drift).
- Exposing secret values in status surfaces.
- Toggling a HITL gate without confirmation or audit row.
- Editing model routing without a cost-impact note (budget discipline, AGENTS.md §3).
- Settings the pipeline cannot read (file-only config diverge).

## Decisions

- Settings live in a `settings` key/value table (JSON values), consumed by the pipeline at run start; collection contracts remain the per-collection source for placement/KPI fields.
- Model routing is deliberately not a settings surface: `pipeline/routing.py` stays the single reviewed source; the Agents screen renders it read-only with a pointer to the change path (spec/PBI + cost-impact note).
- Brand-lock edits stay founder-gated: the UI prompts confirmation and the change is treated as a founder-approved invariant update (AGENTS.md §3), recorded in the audit log.
