# Spec: Distribution — Social + Video + Community flywheel

## Goal
Turn each shipped product into distribution without founder effort: Social Agent posts on a strict cron and ratio, Video Agent produces 8 s product clips via Veo 3.1 Lite, Community Agent monitors and replies in SWE brand voice — all consuming the product_url written by the content pipeline (`listing_copy.json`) and the design PNG, and all respecting platform rules (4:1 value:promo, never link in Reddit post body) so the organic flywheel in docs/06-traffic compounds rather than burns karma.

## Scope
- In scope:
  - Social Agent (`claude-haiku-4-5`, cron `0 11 * * TUE,WED,THU` → 11am ET): consumes `ecommerce_list-offers` product image/URL + `listing_copy.json`; weekly rotation Tue new design drop (image + minimal copy + link in reply only), Wed dev meme/culture (no product, pure relatability), Thu engagement (poll/question/reply-bait); platform rules: Twitter plain text first, link in reply only if >50 likes 24h, Reddit never link in post body (value post only, Karma-first, link in comment reply only if >100 upvotes), ratio 4 value : 1 promo enforced via `content_ratio` counter persisted in `workspace/social_state.json`; `buffer_api` (`https://api.bufferapp.com/1`, `BUFFER_ACCESS_TOKEN`) for scheduling; cross-post design for TikTok/IG is out-of-scope until Video Agent provides clip notes.
  - Video Agent (orchestrator `claude-haiku-4-5` scripting + `google/veo-3.1-lite` via `POST https://openrouter.ai/api/v1/videos` + poll `GET /videos/{job_id}` every 10s, timeout 10m, model `veo-3.1-lite`, duration 8, per docs/02-stack sample): cron 2×/week Mon+Thu 10:00; consumes `product_image_url` from `ecommerce_list-offers` + `slogan`; prompt template `Terminal screen. Green text '[SLOGAN]' types character by character. T-shirt materialises. Dark cinematic. SWE aesthetic. 8 seconds. Ambient keyboard sounds.` (and Dark Cinematic alt per docs), `file_write` clip URL to `workspace/reports/video_clips.json` for Social Agent pickup; timeout → `notifyCEO` + skip product.
  - Community Agent (`claude-haiku-4-5`, cron every 12h `0 */12 * * *`): monitors `twitter_api_v2` mentions/search + `reddit_api` comment/keyword search for keywords `swedrip, swe drip, software engineer shirt, programmer merch, developer shirt` plus any slogan names from `listing_copy.json`; replies in SWE brand voice (match tone sarcastic→dry, enthusiastic→warm), never include product link unless directly asked, never argue with criticism, log all interactions to `workspace/community_log.json` for pattern tracking.
  - Content calendar contract (docs/06-traffic): `Monday 08:00` Trend Scout, `Monday 10:00` CEO approve, `Monday–Tue` Copy+Design+Listing, `Tue 11:00` Social drop via Buffer, `Tue+Thu` Video async, `Wed 11:00` Social meme, `Thu 11:00` Social engagement + Video clip post, `Fri 18:00` Analytics (operations spec), `Sat 09:00` Email (operations), `1st/month 09:00` Finance (operations) — this spec owns the Tue/Wed/Thu + Mon/Thu Video + 12h Community slices.
  - Ratio enforcement + SEO interplay: Social Agent writes `fw_tags` usage count to `program.md` learnings via platform spec's append helper; Listing Agent's tags already cover docs/01-brand SEO tiers (primary/mid/long-tail) — Social does not duplicate SEO.
- Out of scope:
  - Trend/Copy/Design/Listing implementation (in `content-pipeline` spec) except as producer of `listing_copy.json`/`designs/*.png`.
  - Analytics/Email/Finance/reporting + `program.md` compaction/monthly summary (in `operations` spec).
  - Coolify deploy/DSL, workspace schema definitions, program.md compaction (platform-workspace), and Fourthwall theme/SEO tag formula (storefront).

## Contracts (success criteria)
1. **Social cron + ratio are enforced deterministically**
   - `nextSocialSlot(nowUTC)` → `Tue|Wed|Thu 11:00 ET` with rotation `TUE=drop(drop→image+minimal), WED=meme(no product), THU=engagement(poll)`; empty `listing_copy.json.product_url` on TUE causes skip (no link hallucinated). `content_ratio` 4:1 persisted and `assert promoCount*4 <= valueCount` else lint fails — test `tests/distribution.test.js` with fake clock without calling Buffer/Twitter.
2. **Social platform rules are pure guards**
   - `validateTwitterPost(post)` fails if `hashtags` or `link in post body` for WED meme; `validateRedditPost(post)` fails if `url contains swedrip.fourthwall` in `body` (must be `comment_reply` only). `BufferSchedule(posts)` calls `POST https://api.bufferapp.com/1/updates/create` with `BUFFER_ACCESS_TOKEN` exactly; test mocks `fetch`, no real `api.bufferapp.com` in `npm test`.
3. **Video prompt + async poll shape match docs/02-stack**
   - `buildVideoPrompt(product_image_url, slogan)` → template string exactly (green text types, t-shirt materialises, 8s, ambient keyboard). `generate_product_video(image_url, slogan)` `POST https://openrouter.ai/api/v1/videos` body `{model:"google/veo-3.1-lite", prompt, image_url, duration:8}` with `Authorization: Bearer $OPENROUTER_API_KEY`, `pollJob(job_id)` loops `GET /videos/{job_id}` every 10s for ≤60 tries, returns `url` on `completed`, throws `RuntimeError(error)` on `failed`, throws `TimeoutError` after 10m (test uses mocked poll, no live Veo spend).
4. **Community reply rules + keyword log are testable offline**
   - `shouldIncludeLink(reply, context)` → false unless `context.directlyAskedForLink===true`; `matchTone(originalTone)` → dry|sarcastic vs warm per table; every reply appended to `workspace/community_log.json` with `{timestamp, platform, keyword, original_id, reply, tone}`. `keywordMonitor()` scans fixtures `twitter-mentions.json` + `reddit-comments.json` without live API. Test `tests/community.test.js` asserts no ambient self-promo link and that criticism is acknowledged not argued.
5. **Social consumes pipeline output only after Listing confirms**
   - `listOffers()` mock must return at least one `status:active` offer with `imageUrl` and `productUrl` before Social's TUE drop becomes eligible — if `ecommerce_list-offers` empty, Social emits no drop (and logs skip to `weekly_report.md` note, owned by operations spec).

## Anti-patterns
- Do not schedule a product link on Wednesday meme or Thursday engagement slots — ratio is non-negotiable (per docs/06-traffic Content ratio rules).
- Do not post a Reddit submission with `swedrip.fourthwall.com` in the body — always comment-reply only after karma-gated signal.
- Do not use hashtags on Twitter/X (`#` banned — SWE Twitter culture hates them).
- Do not poll Veo without timeout — every poll has 10s cadence and 60-try (10m) guard, notify CEO on timeout.
- Do not call real Buffer/Twitter/Reddit/OpenRouter in `npm test` — all network calls are mocked.

## Decisions
- **Decision-1 — Haiku for Social/Video/Community:** per docs/03-agents cost table ($0.80/$4 per M, $2–4 budgets) — Sonnnet would breach $130 cap with 3×/week + 12h cadence.
- **Decision-2 — Buffer as scheduling seam, Twitter direct only as fallback:** per docs/02-stack Buffer free tier (3 channels, 10 queued) + docs/03-agents Social tools — `BUFFER_ACCESS_TOKEN` is the only social write secret in `npm test` fixtures.
- **Decision-3 — Video via OpenRouter /videos async (not direct Veo API):** matches docs/02-stack `generate_product_video` sample (POST → job_id → GET poll) so spend is unified on OpenRouter cap.
- **Decision-4 — Community tone matching is rule-based not LLM-judged in gate:** tone map is tested as string transform so `npm test` stays deterministic (LLM voice quality is a review gate, not a unit assertion).

## Tooling
- `https://api.bufferapp.com/1` (`BUFFER_ACCESS_TOKEN`), `twitter_api_v2` + `reddit_api` (community), `https://openrouter.ai/api/v1/videos` (Veo), FW MCP `ecommerce_list-offers` (read-only for Social/Video), `file_write`/`file_read` for workspace state.
- Coolify MCP not needed here (distribution is scheduling/posting, not infra).
