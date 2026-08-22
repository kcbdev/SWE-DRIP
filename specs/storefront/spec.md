# Spec: Storefront — Fourthwall Brutal theme, pricing invariants, SEO, launch readiness

## Goal
Make the Fourthwall storefront earn trust at first glance and index for organic search from day 0: Brutal theme with brand-correct CSS lands, hard pricing ($32/$62/$20) is enforced in every `ecommerce_update-offer` call, every listing is keyword-rich for the title formula + 8–12 tags across three SEO tiers, and the launch checklist gates `docs/05-launch.md` (10 products + 3 videos + 20 tweets + ≥50 emails + PH/HN posts + Telegram) before traffic spend is allowed.

## Scope
- In scope:
  - Fourthwall storefront theme (docs/02-stack): apply `Brutal` via `Dashboard → Themes → Brutal → Activate`, custom CSS (Dashboard → Theme → Custom CSS) exactly:
    ```css
    :root { --color-background: #0D0D0D; --color-primary: #00FF41; --color-text: #FFFFFF; --font-display: 'JetBrains Mono', monospace; }
    ```
    Verify contrast (void black bg, terminal green primary, white text, mono display). Logo is mono wordmark per docs/05-launch.
  - Pricing enforcement (docs/01-brand Pricing — hardcoded, founder-only change): `T-shirt $32 | Hoodie $62 | Mug $20 | Stickers 5-pack $9 | Tote $25` with Fourthwall `2.9% + $0.30` fee / `Printful` COGS notes; Listing Agent (content-pipeline) calls are verified here via storefront lint: `scripts/lint.js` extension asserts any `ecommerce_update-offer` price in fixtures equals invariant (else fail) and any doc price-table edit requires ADR + smoke-test update.
  - Merchant-of-Record plumbing verification (docs/02-stack): payments + sales-tax auto + Payouts → PayPal (verified Morocco/PayPal path), Payout → `finance_report.md` (operations spec) — this spec only confirms the storefront's Payout config is reachable (`ecommerce_get-payout-info` returns non-empty, mocked in gate) and that customer support is Fourthwall-hosted (no custom checkout code in this repo).
  - SEO per listing (docs/01-brand SEO targets + 06-traffic + docs/03-agents Listing checks):
    - Title formula: `[Stack/concept] + [Product type] + [Phrase or hook] + [Occasion]` e.g. `Rust Developer T-Shirt | Undefined Behavior | Funny Coding Gift for Programmer` (60 chars max, 2+ keywords from primary/mid tiers).
    - Tags: 8–12 per listing, Tier1 broad 2–3 (`programmer shirt`, `developer gift`, `software engineer shirt`), Tier2 mid 3–4 (`rust programmer shirt`, `python developer shirt`), Tier3 long-tail 4–5 (`funny shirt for software engineer`, `programmer birthday gift`), 13 allowed in `listing_copy.json` schema but storefront lint enforces 8–12 live.
    - Description: 150–200w natural keyword inclusion (checked in content-pipeline but storefront lint cross-checks word count + keyword density ≥2 primary terms).
    - Fourthwall Google indexing: each active listing with rich title+description contributes passively — by month 3, 20–30% traffic from search (no code gate, but `analytics.test.js` checks traffic breakdown label "SEO").
  - Launch readiness gates (docs/05-launch Pre-launch checklist + Launch week day-by-day + Channel tactics):
    - Store checklist: Brutal theme + custom CSS + logo + PayPal payout verified Morocco + email capture "Coming soon — get first access" + shipping US/UK/EU + return policy (Fourthwall default).
    - Content gate: 10 validated designs live on FW (each passed Trend signal + Copy dupe check), 3 product showcase videos (Video Agent), 20 dev-humor tweets pre-scheduled in Buffer (no product links yet), Product Hunt listing drafted (Name+Tagline+Description per docs/05-launch), Show HN draft (architecture angle), launch email drafted in Loops (held).
    - Distribution gate: `@swedrip` Twitter created + bio + pinned tweet, Reddit karma ≥500 from 5 value posts on r/ProgrammerHumor, Buffer connected, Loops template test-sent to self.
    - Launch week playbook (Mon soft launch 10-tweet thread → Tue PH 12:01am PST → Wed Show HN → Thu Reddit r/ProgrammerHumor + r/cscareerquestions no link in post → Fri–Sun momentum), per-channel rules (Twitter Tue–Thu 9–12am ET, no hashtags, reply to Primeagen/Theo/DHH only when relevant; Reddit Mon–Thu 10–14 ET, value-first 4:1). Targets: Email +200, Twitter +500, First sale Day 1, Week1 $300+, PH Top 10 Dev Tools, HN >50 pts — recorded in `weekly_report.md` after launch.
  - Scale storefront obligations (docs/07-scale Product expansion sequence): Launch T-shirt/mug/sticker, Month2 Hoodie after 20+ sales top tee, Month3 Tote/hat after $3k 2mo, Month4 Desk mat/poster on Discord request, Month6 limited/signed on influencer proven — Listing Agent respects `product_types` whitelist per milestone.
- Out of scope:
  - Agent generation logic (Trend/Copy/Design/Listing implementation — in `content-pipeline` spec; this spec audits its storefront side-effects).
  - Social/Video/Community cron execution (in `distribution` spec) and Analytics/Email/Finance reporting (operations) except as launch gate consumers.
  - Coolify domain/TLS for `swedrip.kcb.ma` itself (in `coolify-deploy` spec — this spec's domain is `swedrip.fourthwall.com` storefront).

## Contracts (success criteria)
1. **Brutal theme + CSS are exact and linted**
   - `storefront/brutal.css` (or inline note in `docs/02-stack.md` delta) contains exactly `--color-background: #0D0D0D; --color-primary: #00FF41; --color-text: #FFFFFF; --font-display: 'JetBrains Mono'`; `scripts/lint.js` `storefrontCssCheck()` fails if gradient/shadow or pastel palette appears, or if `README.md`'s Directory section still claims no `storefront/` when `storefront/brutal.css` is landed — test `tests/storefront.test.js` snapshots the CSS string.
2. **Pricing is enforced in every listing and in docs**
   - Any call fixture `ecommerce_update-offer({price})` asserted `price===32||62||20` per product_type (tshirt 32, hoodie 62, mug 20); `docs/01-brand.md` price table's `$32`/`$62`/`$20` assertions remain in `tests/smoke.test.js` — a price change without `docs/adrs/ADR-*.md` "Pricing" ADR fails the gate (brand invariant per AGENTS.md §3).
3. **SEO title + tags per listing meet the formula and tiers**
   - `buildFwTitle({stack, productType, phrase, occasion})` → title ≤60 chars and regex contains at least 2 SEO keywords from `docs/01-brand.md` primary/mid list (e.g. `programmer shirt`, `rust programmer shirt`); `selectTags(phrase)` → array length 8–12 covering Tier1 2–3 + Tier2 3–4 + Tier3 4–5. `listing_copy.json` 13-tag schema is the Copy-side superset, but `ecommerce_update-offer` live call assert 8–12 (lint enforces live <13 display cut). Tested in `tests/seo.test.js` with fixture phrases.
4. **Launch checklist is a green gate, not a vibe**
   - `scripts/verify-launch.js` (or extension to `verify-deploy.js`) reads `workspace/reports/launch_readiness.json` (or enumerates `ecommerce_list-offers` mock returning 10 offers `status:active`) + `Buffer queue count==20` + `Loops draft exists` + `video_clips.json length==3` + `email list >=50` stub → exit 0 only if ALL checklist items `docs/05-launch.md:5` are true; otherwise prints `MISSING: ...` and exits 1 — `npm run verify` chains it (skips if no `launch_readiness.json` until pre-launch PBI lands).
5. **PH/HN drafts are template-exact and channel rules linted**
   - `ph_hunt_draft.md` contains `Name: SWE Drip / Tagline: A clothing brand run entirely by AI agents. No humans involved.` and screenshots list (FW homepage, Paperclip board, Design render, Analytics report) — asserted via `scripts/lint.js` string include. `social_state.json` assert `hashtags===0` and `reddit_posts[0].body.contains('swedrip.fourthwall')===false`.
6. **Scale product expansion respects milestones**
   - `product_typesAllowed(mrr, topSales)` → launch `[tshirt,mug,sticker]` else hoodie only if `topSales>=20` else tote/hat only if `mrr>=3000 && sustained 2mo`, etc. — unit-tested; Listing Agent's `assert product_types subsetOf allowed` else lint fails. No code gate claims scale unlocks without the milestone.

## Anti-patterns
- Do not change pricing without founder ADR — smoke test + storefront lint both enforce the invariant.
- Do not publish a Fourthwall tag set with <8 or >12 live tags, or a title with 0 keywords or >60 chars — violates SEO compounding.
- Do not use non-mono branding (gradients, shadows, pastels, cartoons) — anti-patterns in docs/01-brand Aesthetic constants are lint errors.
- Do not claim launch-ready without 10 live products — the `verify-launch` gate is mandatory before PH/HN posts.
- Do not treat `swedrip.fourthwall.com` as interchangeable with `swedrip.kcb.ma` — former is Fourthwall POD storefront, latter is Coolify-hosted repo/docs (coolify-deploy spec); keep domains distinct in docs and tests.

## Decisions
- **Decision-1 — Storefront correctness is a lint gate, not a deployment:** pricing/CSS/SEO violations fail `npm run lint`/`scripts/lint.js` locally without hitting live Fourthwall — live `ecommerce_*` verification is `manual` (PH/HN traffic proves indexing later).
- **Decision-2 — 10-product pre-launch gate is hardcoded:** per docs/05-launch Launch gate all-must-be-true — no launch PBI moves to `In Review` red.
- **Decision-3 — Brutal theme CSS lives as `storefront/brutal.css` (or doc delta) + lint snapshot, not as custom Next.js:** Fourthwall is Merchant of Record — no checkout/fork.
- **Decision-4 — SEO tag enforcement is 8–12 live, schema allows 13:** per docs/06-traffic Listing Agent 8–12 tags vs docs/03-agents Copy schema `fw_tags[13]` — Copy may propose 13, Listing trims to live 8–12 (lint cross-check).

## Tooling
- Fourthwall MCP `https://mcp.fourthwall.com` (`ecommerce_*`, `brand_from_url`), mocked in tests; Coolify MCP not needed here; `node:test` only.
