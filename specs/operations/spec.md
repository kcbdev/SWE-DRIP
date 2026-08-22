# Spec: Operations — Analytics + Email + Finance + CEO intelligence & drift fix

## Goal
Close the flywheel: Analytics makes the company smarter every Friday, Email tells subscribers what the AI shipped Saturday, Finance reconciles payouts and spend on the 1st, CEO acts on kill/scale/flash-sale rules and reports to the founder via Telegram weekly — while the `program.md` memory stays compact so Trend Scout scores better each week (docs/06-traffic) and scale unlocks fire at the right MRR (docs/07-scale).

## Scope
- In scope:
  - Analytics Agent (`claude-haiku-4-5`, cron `Fri 18:00` Marrakech): read full FW MCP analytics suite (`ecommerce_get-analytics`, `ecommerce_list-offers`, `ecommerce_get-payout-transactions` where relevant) → produce `/workspace/weekly_report.md` (KPI table: Orders, Revenue, Etsy conv rate target 2%, AOV target $35, Top design; sections Kill list (>30 days, 0 sales, auto `ecommerce_update-offer` status→inactive), Scale list (5+ sales <14 days → expand hoodie+mug), Anomalies, CEO recommendations 3 bullets) + `/workspace/kill_list.md`; automated actions without CEO approval: archive kill list via FW MCP, log kill patterns to `program.md` (via platform-workspace append helper), notify CEO via Paperclip task with report summary; also read `program.md` learnings to bias next week's scoring weights.
  - Email Agent (`claude-sonnet-4-6`, cron `Sat 09:00` Marrakech): `Loops.so POST https://app.loops.so/api/v1/campaigns` with `LOOPS_API_KEY`, `FW MCP ecommerce_list-offers` for this week's new products — subject `The Agent Report #[N] — [slogan of the week]` — body: this week Scout found [insight], Copy produced N slogans, shipped N, design [name] story + image+link, what was killed + why, next week's teaser; target open >35%.
  - Finance Agent (`gemini-2.0-flash-001`, cron `1st 09:00`): FW MCP `ecommerce_get-payout-transactions` + `ecommerce_get-payout-info` → `/workspace/finance_report.md` with `Revenue | COGS | FW fee 2.9%+$0.30 | OpenRouter spend | Net %`, Top design by revenue, Payout expected/received dates + MoM change, OpenRouter cap $130 usage %, Action items; escalate to CEO if payout delayed >3d OR OpenRouter spend >80% by 20th OR net margin <40%; Finance report archived weekly to `workspace/reports/archive/` per docs/07-scale Guard it accordingly.
  - CEO weekly loop (Sonnet, always_on + post-Analytics): read `program.md`/`program-summary.md` + `weekly_report.md` → fire kill list (already archived by Analytics — confirm), flag scale list, flash-sale if WoW revenue −30% → `ecommerce_create-promotion` (20% off top 3, per docs/03-agents), write Telegram digest (`POST https://api.telegram.org/bot{TOKEN}/sendMessage` with `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`, Markdown) — weekly founder packet with KPIs + CEO recommendations + spend vs cap — escalate on `spend>$50 single decision / ban / payout issue / viral >10k`.
  - Program drift fix (monthly, 1st, Email Agent secondary task per docs/07-scale): `Summarize program.md → program-summary.md` — keep Winning patterns (active), merge duplicates, archive >90d unreinforced patterns to `## Archive`, keep all Kill rules (hard constraints), trim Agent performance log to last 3 months, max 500 lines; CEO switches to reading `program-summary.md` after month 3.
  - Scale arithmetic + unlocks (docs/07-scale): at $10k MRR math `AOV $38 ×50% margin ×526 orders/mo (18/d) → 21k visitors @2.5% conv` broken down by channel (SEO 28%, Twitter 24%, Email 14%, Reddit 14%, Collabs 10%, TikTok 10%) — Analytics report shows traffic breakdown + pipeline for scale gate decisions; unlock table `$500 break-even → $1k newsletter → $2k collab → $3k stack-limited 48h drop → $5k paid (Reddit $300+Twitter $200, CAC <$12) → $8k influencer rev-share → $12k Discord #vote-next → $20k physical retail` — CEO draft outreach templates, Community Agent finds targets.
- Out of scope:
  - Trend/Copy/Design/Listing/Social/Video/Community execution (in `content-pipeline` + `distribution` specs) except as data producers/consumers via workspace files.
  - Coolify infra/domain/TLS (`coolify-deploy`) and workspace schema definitions themselves (`platform-workspace`) except via their APIs.
  - Actual Fourthwall payment capture or Payslip PayPal delivery (Finance reports, not disburses).

## Contracts (success criteria)
1. **Weekly report structure and auto-actions are exact**
   - `buildWeeklyReport(analyticsFixture)` outputs markdown with exact headers `## KPIs | ## Kill list (0 sales, >30 days) | ## Scale list (5+ sales, <14 days) | ## Anomalies | ## CEO recommendations (3 bullets)` and the KPI table columns `This Week | Last Week | Target | Status`; `kill_list.md` is the filtered list. With fixture `offers: [{daysSincePublish:31, sales:0}]`, the test asserts `ecommerce_update-offer status:inactive` is called exactly once (mocked FW MCP) and `program.md` append of `kill:"{design}" 0 sales 31d` fires — `tests/analytics.test.js`.
2. **Email Agent shape matches Loops.so contract**
   - `send_newsletter(subject, html, listId)` → `POST https://app.loops.so/api/v1/campaigns` with `Authorization: Bearer $LOOPS_API_KEY`, body `{subject: "The Agent Report #[N] — ...", html, listId}` — test mocks `fetch`, no live `app.loops.so`. Subject prefix and body sections (this week insight + shipped count + product image/link + killed + teaser) asserted via snapshot `tests/email.test.js`.
3. **Finance report + escalation guards are pure functions**
   - `buildFinanceReport({revenue, cogs, fee, openRouterSpend})` → `Net% = (revenue-cogs-fee-openRouterSpend)/revenue` and strings match `Finance Report — [Month Year]` header; `shouldEscalate({payoutDelayDays, spendPctDay20, netMargin})` → true if `delay>3 || spendPct>0.80 && day>=20 || netMargin<0.40` — unit-tested with MoM change calc, no FW call in gate. `workspace/reports/archive/` path asserted on write.
4. **CEO decision rules + Telegram digest are tested without LLM**
   - Reuses `platform-workspace:3` pure functions `decideKill/Scale/FlashSale` — operations suite adds `postWeeklyDigest(report) → Telegram POST https://api.telegram.org/bot$TOKEN/sendMessage {chat_id:$CHAT_ID, text: markdown, parse_mode:"Markdown"}` with `weekly_report.md` + `finance_report.md` snippet; escalations `spend>50 | ban | payout | viral>10k` short-circuit to `notify_founder` (mocked `httpx.post`, no real `api.telegram.org` in `npm test`).
5. **Program drift compaction respects 500-line guard and Archive semantics**
   - Given `program.md` with 600 lines containing duplicate `Winning patterns` + >90d unreinforced `Stale pattern: Rust Edition` + 4-month Agent log, `compactProgram(programMd)` → `program-summary.md` ≤500 lines, duplicates merged, stale moved to `## Archive`, kill rules retained verbatim, log trimmed to last 90d — test `tests/operations-drift.test.js` asserts line count and section presence without calling any MCP.
6. **Scale unlock arithmetic is computed, not hallucinated**
   - `ordersNeeded(mrr=10000, aov=38) → 263 // 526 for gross?` and `visitorsNeeded(orders, conv=0.025) → 10526 // 21040` match docs/07-scale block `21,000/month` within ±5%; channel split percentages sum to 100% and each has expected label (SEO/Twitter/Email/Reddit/Collabs/TikTok) — linted in `tests/operations.test.js`.

## Anti-patterns
- Do not archive a design with sales >0 or age ≤30d — kill is `0 sales AND >30 days` only.
- Do not send Email Agent digest without `weekly_report.md` existing — `weekly_report.md` is the input, not optional.
- Do not let Finance write payout dates in any format other than `YYYY-MM-DD` ISO 8601.
- Do not emit `program-summary.md` without trimming to 500 lines — CEO context blowup is the scale killer.
- Do not escalate on normal variance — only `spend>50`/`ban`/`payout`/`viral>10k` trigger Telegram founder ping.

## Decisions
- **Decision-1 — Haiku for Analytics/Community/Finance, Sonnet for Email/CEO:** per docs/03-agents budget caps ($3/$4 vs $30) and quality bar for founder-facing prose (The Agent Report open rate) — deterministic `npm test` mocks the Sonnet output.
- **Decision-2 — Loops via `app.loops.so/api/v1/campaigns` + FW MCP payout suite via `ecommerce_get-payout-*`:** exactly docs/02-stack + docs/03-agents wiring — no Loops SDK needed, just `httpx`/`fetch`.
- **Decision-3 — Monthly `program.md` compaction is an Email Agent secondary cron (1st):** per docs/07-scale Solution — not a separate agent, keeps agent count 11.
- **Decision-4 — CEO reads `program-summary.md` after 90d, not `program.md`:** per docs/07-scale long-term moat — `program.md` backup stays durable (`/root/backups` + `workspace/reports/archive/`), but LLM context is the summary.

## Tooling
- FW MCP analytics/payout/promotions suite, Loops.so `https://app.loops.so/api/v1`, Telegram `https://api.telegram.org/bot.../sendMessage`, `file_write`/`memory` for `program.md`, Coolify MCP not needed here (operations is data/notify, not infra).
