# Spec: Fourthwall Store — MCP-native storefront, design, and first products

## Goal
SWE Drip's storefront is **Fourthwall-hosted end to end** (no custom storefront code): Brutal theme designed per brand constants, organized into collections, and operated by Paperclip agents through the **Fourthwall MCP server** (`https://mcp.fourthwall.com`, Streamable HTTP, OAuth 2.0). The repo keeps contracts + SOUL sources; Fourthwall keeps commerce; Paperclip agents keep operations.

## Scope
- In scope:
  - Connect Fourthwall MCP inside Paperclip so Design/Listing/Analytics/Finance/Social/CEO can call `ecommerce_*` and `brand_*` tools (OAuth login by founder on first connect)
  - Storefront design implementation: activate **Brutal theme**, inject brand Custom CSS (`--color-background:#0D0D0D; --color-primary:#00FF41; --color-text:#FFFFFF; --font-display:'JetBrains Mono',monospace`), mono wordmark logo, shop site set **online**
  - Collections created via MCP (`ecommerce_create-collection`): "Terminal Collection" (default) + "Stack-Specific" (Rust/Python/Go drops)
  - First live product through the MCP design pipeline: `ecommerce_generate-product-design-previews` → `ecommerce_create-offers-from-designs` → price/tags/collection via `ecommerce_update-offer` ($32 tee invariant) → published at `swedrip.fourthwall.com`
- Out of scope:
  - Any custom storefront code, checkout, or hosting in this repo (repo serves docs only)
  - Static-token auth (`docs/02-stack.md`'s `FOURTHWALL_MCP_TOKEN` assumption is corrected by this spec: FW MCP uses OAuth browser flow)
  - Social/email/promo content execution (distribution spec owns cadence; CEO may create promotions via `ecommerce_create-shop-promotion` when kill/scale rules fire)

## Contracts (success criteria)
1. **MCP connected & callable from Paperclip** — a Design Agent test task successfully calls `ecommerce_get-current-shop` and returns the SWE Drip shop record.
2. **Storefront is branded** — visiting the Fourthwall storefront shows void-black background `#0D0D0D`, terminal-green primary `#00FF41`, JetBrains Mono display type (inspect rendered HTML/CSS or founder visual confirm), logo wordmark set.
3. **Collections exist** — `Terminal Collection` + `Stack-Specific` retrievable via `ecommerce_get-collections`.
4. **First product live at invariant price** — ≥1 t-shirt offer `status:active`, price `$32`, assigned to Terminal Collection, visible on the public storefront.
5. **Shop online** — `swedrip.fourthwall.com` returns 200 publicly (not password-protected/offline).

## Anti-patterns
- Do not fork/clone the storefront or build custom HTML checkout.
- Do not publish products before Brutal theme + CSS are applied (first impression is permanent).
- Do not bypass OAuth — never ask founder to paste FW credentials into chat.
- Do not create products outside collections or off-price ($32/$62/$20 invariants).

## Decisions
- **Decision-1 — OAuth over static token:** FW MCP authenticates per-session via browser OAuth; founder performs one-time login in Paperclip's MCP settings. Corrects `docs/02-stack.md` token assumption.
- **Decision-2 — Theme/CSS via Fourthwall dashboard:** theme activation + Custom CSS injection are dashboard operations (not exposed as MCP tools); product/collection/promotion operations are MCP-driven.
- **Decision-3 — Brand assets via MCP brand tools:** `brand_from_url` on `https://swedrip.kcb.ma` builds the brand profile; wordmark/logo extracted via `brand_extract_assets` where needed.

## Tooling
- Fourthwall MCP (`https://mcp.fourthwall.com`) attached inside Paperclip settings.
- Verification helpers: direct HTTPS probes of `swedrip.fourthwall.com`; `ecommerce_get-collections` / `ecommerce_get-offers` reads.
