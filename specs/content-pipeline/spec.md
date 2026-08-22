# Spec: Content Pipeline — Trend Scout → Copy → Design → Listing

## Goal
Ship a new product in <24 h from a validated SWE-cultural brief with zero human touch: Trend Scout finds a scored phrase, Copy Agent crafts ≤6-word slogan + SEO listing, Design Agent renders a print-safe FLUX.2 Pro PNG on OpenRouter and publishes via Fourthwall MCP, Listing Agent prices/tags/collections and confirms live — the critical path from docs/03-agents (Copy/Design/Listing marked on-task) and docs/06-traffic flywheel first four steps.

## Scope
- In scope:
  - Trend Scout (`gemini-2.0-flash-001`, Mon 08:00 Marrakech via cron): scan `reddit_rss` (r/ProgrammerHumor, r/cscareerquestions, r/webdev, r/rust, r/golang) + `twitter_search_v2` + `web_search` (Fourthwall/TeePublic dupe check, Etsy dupe check), score each brief `engagement 0–40 + novelty 0–30 + specificity 0–30 = 0–100`, only surface `score>60`, never recycle 60-day phrase, flag offensive for CEO review, write `/workspace/design_briefs.json`. Include before-design validation gates (Reddit >100 upvotes 24h OR Twitter >50 likes, Etsy/FW exact phrase not saturated — per docs/01-brand Validation process).
  - Copy Agent (`claude-sonnet-4-6`, on_task after CEO approves brief ≥60): read `design_briefs.json` → produce `listing_copy.json` with `{brief_id, primary_slogan ≤6w, slogan_variants[3], fw_title ≤60 chars keyword-rich, fw_description 150–200w SWE voice benefits-led, fw_tags[13], design_prompt_notes "JetBrains Mono Bold #00FF41 on #0D0D0D centered terminal", product_types [tshirt,hoodie,mug]}`, enforce "Would a senior SWE DM this to team chat?" and "Never explain the joke" + identical-phrase check on FW/TeePublic before approve.
  - Design Agent (critical path, `black-forest-labs/flux.2-pro` via `POST https://openrouter.ai/api/v1/images` → base64 PNG 2048×2048, fallback `google/gemini-3.1-flash-image`, prompt template from docs/03-agents: `Minimalist apparel design. Typography: JetBrains Mono Bold. Text: "[SLOGAN]". Color: Terminal green #00FF41 on void black #0D0D0D. Centered isolated. No decorations. No gradients. Print-safe flat.`; save `/workspace/designs/[brief_id].png` (validate RGB not RGBA, <10MB, ≤2000×2000 per troubleshooting), then FW MCP `ecommerce_generate-product-design-previews` → verify mockup → `ecommerce_create-offers-from-designs` → live product; write product URL back to `listing_copy.json` for Social Agent; retry policy 1 retry with fallback then `notify_founder` via Telegram on double-fail).
  - Listing Agent (`gemini-2.0-flash-001`, on_task after Design confirms): FW MCP `ecommerce_update-offer` + `ecommerce_list-collections` — set price per hard invariant ($32 tee / $62 hoodie / $20 mug), apply `fw_tags`, assign correct collection (e.g. Terminal Collection vs Stack-Specific), set `fw_description`, `status:active`, confirm live at `swedrip.fourthwall.com/products/[slug]` (accessible).
  - Fourthwall MCP surface (docs/02-stack): server `https://mcp.fourthwall.com`, OAuth `FOURTHWALL_MCP_TOKEN`, tools `ecommerce_generate-product-design-previews`, `ecommerce_create-offers-from-designs`, `ecommerce_update-offer`, `ecommerce_list-collections`, `brand_from_url`; Brutal theme custom CSS handled in `storefront` spec but brand constants read here.
  - OpenRouter single-key routing (docs/02-stack): `Authorization: Bearer $OPENROUTER_API_KEY` at `https://openrouter.ai/api/v1` (chat `/chat/completions` for LLM, `/images` for FLUX, `/videos` polled later in distribution).
- Out of scope:
  - Social/Video posts about the product (in `distribution` spec — Social Agent picks up `listing_copy.json` product_url after Listing confirms).
  - Analytics kill/scale decisions (in `operations` spec — Analytics reads `ecommerce_get-analytics` after publish).
  - Coolify deploy plumbing (`coolify-deploy` spec) and workspace/program.md lifecycle (`platform-workspace` spec) except as file inputs.

## Contracts (success criteria)
1. **Trend Scout scoring is deterministic and validated**
   - Given fixture reddit/twitter JSON, `scoreBrief(brief)` returns 0–100 with exact `score_breakdown` per rubric; `score>60` + no 60-day repeat + not already on Etsy exact search + at least one signal check (Reddit>100 or Twitter>50) else suppressed — unit test `tests/trend-scout.test.js` uses fixture `reddit-rss-sample.json` without network. Flagged phrases never auto-write to `design_briefs.json` without CEO `approve`.
2. **Copy slogan ≤6 words and dupe-free**
   - `validateCopy(copy)` fails if `primary_slogan.split(/\s+/).length >6`, if dupe check `fw_searchExact(phrase)` hits FW/TeePublic, or if `fw_title.length>60`; `fw_description` 150–200 words and `fw_tags.length===13` — lint + test `tests/copy-agent.test.js`. Full pipeline dry-run `Copy Agent → /workspace/listing_copy.json` with one approved brief produces valid JSON and leaves `product_url` null until Design Agent fills it.
3. **Design PNG is print-safe and retry is correct**
   - `generate_design(slogan, model=flux.2-pro)` builds exact prompt template (JetBrains Mono Bold, #00FF41 on #0D0D0D, 2048×2048, flat) and `httpx.post` shape matches docs/02-stack sample (headers `Authorization: Bearer ...`, `image_config {2048,2048}`, timeout 120s). On `429`/`5xx`, retry once with fallback model `google/gemini-3.1-flash-image` + simplified fallback prompt (`Large bold white monospace text "..." centred on solid black...` per docs/04-deploy troubleshooting); second failure calls `notify_founder`. Output PNG validated: mode RGB (raise if RGBA), size <10MB, dimensions ≤2048, not RGBA. Test uses httpx mock, no real OpenRouter spend.
4. **Fourthwall MCP publish is zero-human-touch and verifiable**
   - Sequence `ecommerce_generate-product-design-previews` (store preview URL returned) → `ecommerce_create-offers-from-designs` (offer id returned) is recorded in `workspace/listing_copy.json[0].product_url`; Listing Agent then `ecommerce_update-offer` price = brand table exactly, tags set, collection assigned, `ecommerce_list-offers` shows `status:active`. E2E `node scripts/pipeline-dry-run.js --brief-id <id>` exercises the mocked FW MCP without hitting prod (mock token).
5. **Scheduling and input ordering are enforced by file contracts**
   - `design_briefs.json` is written only on Mon 08:00 trigger (enforced by cron label in agent SOUL.md, not code gate, but `git log` shows `scripts/crons.json` has `trendScout: "0 8 * * MON"`); pipeline `Copy→Design→Listing` respects `listing_copy.json.product_url` null→set ordering.

## Anti-patterns
- Do not bypass the Reddit/Twitter signal threshold and publish an unvalidated phrase to FLUX — validation gates exist before spend.
- Do not hardcode slogan text in prompts with decoration — prompt is `Minimalist apparel design. JetBrains Mono Bold... #00FF41 on #0D0D0D. Centered isolated... Print-safe flat.` only (and tested fallback).
- Do not run Design before Copy produced `listing_copy.json` — file contract ordering is the guardrail.
- Do not bypass `brand_from_url` consistency check after preview generation when the tool is available.
- Do not set prices other than $32/$62/$20 — Listing Agent `assert price===BRAND_PRICE[product_type]` else fail.

## Decisions
- **Decision-1 — Gemini Flash for Scout/Listing, Sonnet for Copy:** per docs/03-agents cost table ($0.075 vs $3 per M) — Scout/Listing are high-frequency, Copy quality justifies Sonnet.
- **Decision-2 — FLUX.2 Pro primary with gemini-3.1-flash-image fallback:** per docs/03-agents Design retry policy; fallback prompt is the white-mono-on-black text-safe variant.
- **Decision-3 — Mock FW/OpenRouter in tests, no live spend in gates:** deterministic `npm test` never calls real `https://openrouter.ai`/`https://mcp.fourthwall.com` — live verification is manual `node scripts/pipeline-dry-run.js --live --brief-id ...` with `FOURTHWALL_MCP_TOKEN` redacted in logs.
- **Decision-4 — PNG validation (RGB, <10MB, ≤2048):** per docs/04-deploy troubleshooting "PNG format issue" fix.

## Tooling
- OpenRouter `https://openrouter.ai/api/v1` (LLM/image) via `httpx` (or node `fetch`) — single `OPENROUTER_API_KEY` used as `OPENAI_API_KEY` + `OPENAI_BASE_URL` per Coolify env, documented in specs/coolify-deploy.
- Fourthwall MCP `https://mcp.fourthwall.com` + OAuth — mocked in tests, Coolify MCP server view is optional aid.
- `file_write`/`file_read` for workspace JSON, `web_search`/`reddit_rss`/`twitter_search_v2` via fixtures.
