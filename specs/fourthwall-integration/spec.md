# Spec: Fourthwall Integration

## Goal

Integrate the Fourthwall system of record per Vision doc §4: reads (orders/analytics/product status) via the Fourthwall Platform Open API; a product-create mechanism decided by spike evidence (MCP write vs hand-rolled Open API); and the final publish cutover from the retired Paperclip/Hermes path to this pipeline (A13–A15).

## Scope

- In scope: Open API read client (HTTP Basic shop credentials); product-create spike + decision record (ADR-004); implementation of the decided create mechanism behind the pipeline's injected Fourthwall interface; publish cutover to `PUBLIC` through the pipeline; old-path deactivation verification.
- Out of scope: storefront UI/catalog/checkout (Fourthwall owns); Channel API/multi-shop; any Control Panel-initiated Fourthwall writes.

## Contracts (success criteria)

- **C1 — Reads**: a typed Fourthwall read client (orders, analytics, product status) authenticated server-side against the Fourthwall Platform Open API (`https://api.fourthwall.com/open-api/v1.0/*`) with shop-level HTTP Basic credentials; read failures degrade gracefully (explicit error/stale state surfaced — never fabricated data or crashes). *(Revised 2026-09-15 by ADR-005: the official MCP server `mcp.fourthwall.com` is OAuth-2.0-interactive-only and cannot accept a configured static credential, so it is not the v1 read path.)*
- **C2 — A13**: a documented decision (ADR-004) on which mechanism handles product-create — MCP write tool if its parameter coverage matches the placement matrix (front/back/sleeve, multi-region), else the hand-rolled Open API flow — with concrete evidence, not assumption. *(Decided 2026-09-15: **hand-rolled Platform Open API** — API keys have full write access, `placementStrategy`/`colors`/`regions` cover the matrix, `publishOnCreate:false` preserves DRAFT-first. The MCP live spike was not run: ADR-005 proved the MCP is OAuth-interactive-only, so the spike would have required building the losing alternative first.)*
- **C3 — Single write path (CC-2)**: product creation happens only inside the pipeline's FW-create node through the decided mechanism; the Control Panel cannot create products through any path.
- **C4 — A14**: one real product published end-to-end through the pipeline, Shelf price-invariant passing automatically, appearing correctly in Fourthwall.
- **C5 — A15**: the old Paperclip/Hermes publish path is verified inactive before this phase closes (no dual-write risk), with evidence recorded.
- **C6 — Invariants first**: no Fourthwall write is attempted before the Shelf check passes; prices at the write call site derive from the shelf/contract, never literals.
- **C7 — Secrets**: Fourthwall credentials exist only server-side (deployment env and/or the server-side settings store); never in frontend bundles, logs, or audit payloads. The integrations status endpoint is presence-only.

## Anti-patterns

- Assuming MCP write coverage without the spike.
- Any second product-create path (scripts included) reaching production data.
- Publishing with a price not enforced by the Shelf node.
- Hotlinking Fourthwall assets or exposing tokens to the client.
- Treating reads as authoritative mirrors of local state (Fourthwall is the system of record).

## Decisions

- Product-create mechanism (ADR-004, Accepted 2026-09-15): the **hand-rolled Platform Open API flow** (`/open-api/v1.0/media/upload-url` → GCS `PUT` → `/media/images` → `POST /products` with `type:"design"`, `regions[]`, `publishOnCreate:false`), implemented once behind the pipeline's injected Fourthwall interface. No MCP write calls in production. `scripts/fw_create_spike.py` is superseded and is not evidence.
- The MCP **write** spike is retired: it was conditional on an MCP session that requires an interactive OAuth connect flow (ADR-005), i.e. building the rejected alternative to evaluate it.
- Read credential lifecycle (ADR-005): a shop Open API user (username + password, HTTP Basic) is configured once — via the deployment env (`FOURTHWALL_API_USERNAME`/`FOURTHWALL_API_PASSWORD`, optional `FOURTHWALL_API_BASE_URL`) or, preferably, the Control Panel Settings → Integrations form (server-side store, overrides env). No refresh cycle exists, so no runbook refresh step is required. Rotation = new credentials saved in Settings.
