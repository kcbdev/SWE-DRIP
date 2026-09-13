# Spec: Catalog & Analytics

## Goal

Surface the Fourthwall-sourced catalog read-mostly with price-invariant status (FR-15), make order/sales events actionable for analytics (FR-16), and provide per-collection KPI dashboards plus the webhook-driven Analytics trigger that replaces polling (A17).

## Scope

- In scope: catalog mirror API + Catalog screen (price-invariant pass/fail, order history); analytics API + screens (per-collection KPI time series vs contract thresholds, revenue vs break-even); Fourthwall order/checkout webhook endpoint feeding the Analytics trigger; retirement recommendation data.
- Out of scope: catalog/pricing writes (Shelf node alone); storefront UI; the retire action itself (collections screen); payment processing.

## Contracts (success criteria)

- **C1 — Catalog mirror**: product list/detail sourced from Fourthwall reads, each showing price-invariant status ($32/$62/$20 pass/fail) computed server-side, plus order history; read-only; stale/error states explicit.
- **C2 — KPI analytics**: per-collection time series (units, conversion) plotted against that contract's own `kpi_thresholds`; overall revenue against the break-even line.
- **C3 — A17**: an order/checkout webhook triggers an Analytics run and updates the affected collection's KPI status without manual polling.
- **C4 — Retirement recommendations**: collections below threshold at `eval_window_days` get a recommendation surfaced for approve/override — never auto-executed; the survivor exception remains a founder choice (mechanics in collections spec).
- **C5 — Webhook integrity**: events are authenticated (signature/secret), idempotent on replay, and rejected when unverifiable.
- **C6 — Read/write discipline**: this surface never writes to Fourthwall; catalog data is a mirror of the system of record, not a local authority.

## Anti-patterns

- Polling as the primary analytics trigger.
- Writing prices/products/catalog state from analytics or catalog code paths.
- Client-side-only price-invariant checks (server must flag).
- Auto-retiring a collection or archiving products without founder action.
- Trusting unauthenticated webhook payloads or processing duplicates twice.

## Decisions

- Analytics runs are triggered by Fourthwall webhooks plus scheduled pulls for catch-up; both paths share one trigger module.
- KPI math derives from MCP-read order data; the checkpointer/audit log remain the sources for pipeline-side facts (no duplication).
