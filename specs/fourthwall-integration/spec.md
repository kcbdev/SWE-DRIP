# Spec: Fourthwall Integration

## Goal

Integrate the Fourthwall system of record per Vision doc §4: reads (orders/analytics/product status) via the official Fourthwall MCP server; a product-create mechanism decided by spike evidence (MCP write vs hand-rolled Open API); and the final publish cutover from the retired Paperclip/Hermes path to this pipeline (A13–A15).

## Scope

- In scope: MCP read client (OAuth2); product-create spike + decision record (ADR-004); implementation of the decided create mechanism behind the pipeline's injected Fourthwall interface; publish cutover to `PUBLIC` through the pipeline; old-path deactivation verification.
- Out of scope: storefront UI/catalog/checkout (Fourthwall owns); Channel API/multi-shop; any Control Panel-initiated Fourthwall writes.

## Contracts (success criteria)

- **C1 — Reads**: a typed Fourthwall MCP read client (orders, analytics, product status) authenticated via OAuth2 server-side token; read failures degrade gracefully (explicit error/stale state surfaced — never fabricated data or crashes).
- **C2 — A13**: the spike produces a documented decision (ADR-004) on which mechanism handles product-create — MCP write tool if its parameter coverage matches the placement matrix (front/back/sleeve, multi-region), else the hand-rolled Open API flow — with concrete evidence, not assumption.
- **C3 — Single write path (CC-2)**: product creation happens only inside the pipeline's FW-create node through the decided mechanism; the Control Panel cannot create products through any path.
- **C4 — A14**: one real product published end-to-end through the pipeline, Shelf price-invariant passing automatically, appearing correctly in Fourthwall.
- **C5 — A15**: the old Paperclip/Hermes publish path is verified inactive before this phase closes (no dual-write risk), with evidence recorded.
- **C6 — Invariants first**: no Fourthwall write is attempted before the Shelf check passes; prices at the write call site derive from the shelf/contract, never literals.
- **C7 — Secrets**: Fourthwall credentials exist only in server-side env; never in frontend bundles, logs, or audit payloads.

## Anti-patterns

- Assuming MCP write coverage without the spike.
- Any second product-create path (scripts included) reaching production data.
- Publishing with a price not enforced by the Shelf node.
- Hotlinking Fourthwall assets or exposing tokens to the client.
- Treating reads as authoritative mirrors of local state (Fourthwall is the system of record).

## Decisions

- The spike is a manual/live step (real credentials, sandbox-safe where possible); its outcome is binding for PBI-027's implementation and recorded in ADR-004.
- OAuth2 token lifecycle at v1: token supplied via server env (`FOURTHWALL_MCP_TOKEN`) with documented refresh procedure in the deployment runbook (deployment PBI later).
