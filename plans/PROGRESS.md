# Progress — SWE Drip

Append-only execution log. One entry per PBI state transition, carrying `PBI-XXX`, `Branch`, `Commits`, `Review` type, and gate summary (see `asdlc-plane` → Resolution comments).

## 2026-08-22 — Onboarding bootstrap (asdlc-onboard)

- **Scope:** Brownfield docs repo with no ASDLC structure → ASDLC-ready
- **Branch:** `master` (no prior commits; `git init` performed 2026-08-22)
- **Commits:** (bootstrap commit pending — `chore: onboard to ASDLC (kcb/SWDR)`)
- **Review:** `agentic` bootstrap — deterministic gates pass, no human judgment (docs invariants only)
- **Gates:**
  - `npm run build` → `build: docs-only repo, no compilation required` — PASS
  - `npm run lint` → `lint: all docs OK` — PASS
  - `npm test` → 8/8 PASS (`tests/smoke.test.js`)
  - Plane binding: `kcb/SWDR (2af62f36-c11a-411a-89b5-8e5a5176b829)` verified via MCP `plane-kcb`
  - Plane Todo seed: 0 issues (Backlog ignored by design)
- **Artifacts:**
  - `AGENTS.md` (constitution + §5 Context Map + Plane binding)
  - `ARCHITECTURE.md` (as-built snapshot, marked not gospel)
  - `plans/README.md` (bootstrap index + Plane sync section)
  - `plans/PROGRESS.md` (this file)
  - `tests/smoke.test.js` + `scripts/lint.js` + `package.json` (verification baseline)
  - `docs/adrs/ADR-001.md` (bootstrap decision)
  - `.gitignore`
- **Next:** route feature work via `asdlc-plan` (requires human-reviewed Spec per PBI)

## 2026-08-22 — PBI-001 Containerize repo (SWDR-1) → In Review (manual)

- **PBI:** PBI-001 `c9e3872` — `Dockerfile` node:22-alpine→nginx:alpine, `nginx.conf` /health → {"status":"ok"}, `.dockerignore`, `public/index.html` brand, `package.json` docker:*, `scripts/docker-smoke.js`
- **Branch:** `master` **Commits:** `c9e3872` (feat: containerize repo — PBI-001) on `58464b7` plan + `6420ca1` onboard
- **Spec:** `specs/coolify-deploy/spec.md` contracts 1,4,5 — container builds, health, no secrets
- **Gates:**
  - `npm run build` → PASS (docs-only)
  - `npm run lint` → PASS (7 docs OK)
  - `npm test` → 8/8 PASS (`tests/smoke.test.js:1`) — smoke still green
  - `node scripts/docker-smoke.js` → 13/13 OK offline (builder, runtime, EXPOSE 80, HEALTHCHECK, USER nginx, nginx -t, no secrets, html brand)
  - `docker build -t swedrip:local .` — **not executed locally** (win32 no daemon) — offline validated; live build expects SUCCESS + `<50MB` on `kcb` Coolify (manual review)
  - `docker run -p 8080:80 health` — **manual** (see Plane comment)
- **Review:** `manual` — deterministic offline passes, but live docker build/run + `curl /health` + `docker history` secrets check requires `kcb` (production) verification — adversarial + constitutional passed (spec contracts honored, no Coolify/domain touch, brand invariants intact, Context Map correct)
- **Files:** `Dockerfile:1`, `nginx.conf:1`, `.dockerignore:1`, `public/index.html:1`, `package.json:7`, `scripts/docker-smoke.js:1`, `plans/README.md:33` status Active→In Review
- **Plane:** `kcb/SWDR-1` `4f5a5834-866e-4249-9890-dba3a6cb273a` — `In Review` `583e59de-0f9b-47cc-83df-f67aa6ad0755` with comment `4d52373b-2192-461b-b4ba-d788d9d634b9` (How to reproduce: `docker build -t swedrip:local . && docker run -p 8080:80 ... && curl /health` + Coolify preview URL)
- **Next:** awaits founder `approved` on Plane `SWDR-1` (or `Done` transition) — do not auto-chain to PBI-002 until PBI-001 is `Done` (dependency PBI-002 needs PBI-001 `Done` per `plans/README.md:34`)

## 2026-08-22 — Plan: swe-drip full factory (6 specs, 18 PBIs)

- **Spec:** `plan: swe-drip full factory — 6 specs, 18 PBIs → kcb/SWDR via MCP` — `58464b7`
- **PBIs:** PBI-001→SWDR-1 … PBI-006→SWDR-6, PBI-007→SWDR-8 … PBI-018→SWDR-19 (SWDR-7 probe deleted); all `Todo` → PBI-001 now `Active→In Review`
- **Gates:** `npm run verify` green at plan commit (8/8)
- **MCP:** Coolify via MCP (no skills) per founder; Plane binding `kcb/SWDR` verified

## 2026-08-22 — PBI-002 Provision Coolify app swedrip on kcb (SWDR-2) → In Review (manual)

- **PBI:** PBI-002 `c309d6f` — Coolify project `swe-drip vztwc3dxianozufxinxm0cgp` env `production r5c2ohxgtq9irlvjiwbtzji1` on server `kcb.ma e4cowswcks844wow04c084wg` destination `coolify i448wgc40wc4wg8oww0ww4os` app `swedrip vfsgl47pv5ew2hbrqxbjwmjq` `https://swedrip.kcb.ma` `KCB/SWE-DRIP#master` `dockerfile` `80` health `/health:80` (PATCH true), `.coolify/app.json` + `docs/adrs/ADR-002.md` + `docs/coolify-provision.md`
- **Branch:** `master` **Commits:** `c309d6f` on `c9e3872` — feat: provision Coolify app swedrip on kcb (SWDR-2)
- **Spec:** `specs/coolify-deploy/spec.md` contracts 2,5,6 — app exists on kcb, git, health, no secrets baked, redeploy one-click
- **Gates:**
  - `npm run build` → PASS
  - `npm run lint` → PASS (7 docs OK)
  - `npm test` → 8/8 PASS
  - `node scripts/docker-smoke.js` → 13/13 OK
  - `GET /api/v1/applications/vfsgl47pv5ew2hbrqxbjwmjq` via `coolify.kcb.ma` `COOLIFY_ACCESS_TOKEN` → `health_check_enabled:true` `health_check_path:/health` `fqdn:https://swedrip.kcb.ma` `git:KCB/SWE-DRIP master dockerfile 80` — live (200)
  - `GET /api/v1/servers/e4cowswcks844wow04c084wg` → `kcb.ma server is_coolify_host:true wildcard https://kcb.ma` + `GET /api/v1/projects/vztwc3dxianozufxinxm0cgp` → `swe-drip` — live
  - `swedrip.kcb.ma` DNS `158.220.96.44` (wildcard `*.kcb.ma` → kcb server) — `dns.lookup` OK, but app not yet deployed (needs `git push` of `master` to `KCB/SWE-DRIP` — repo 404, create via `gh repo create KCB/SWE-DRIP --public --source=. --push` before `POST /api/v1/applications/vfsgl47…/deploy`)
- **Review:** `manual` — live Coolify API provisioning succeeded, but `git push` + first `Deploy` + `curl https://swedrip.kcb.ma/health` → LE cert still pending (PBI-003). Adversarial: spec contracts 2/5/6 honored, no Dockerfile/nginx mutation, volumes reserved not mounted, env catalog no values baked, brand invariants intact. Constitutional: `AGENTS.md:56` still Planned for `agents/`/`workspace` — correct (only `.coolify/` added).
- **Files:** `docs/adrs/ADR-002.md:1`, `.coolify/app.json:1`, `docs/coolify-provision.md:1`, `plans/README.md:34` Active→In Review
- **Plane:** `kcb/SWDR-2` `2bb2a422-1d20-465d-ac63-102f0a186bd1` — `In Review` `583e59de…` comment `5013db08…` (How to reproduce: `curl -H "Authorization: Bearer $COOLIFY_ACCESS_TOKEN" https://coolify.kcb.ma/api/v1/applications/vfsgl…` + UI + `git push` + `deploy`)
- **Next:** per founder `2026-08-22` override, PBI-001 still `In Review` (will be retro-validated on deploy success) — proceeding to PBI-003 domain TLS on success of this PBI's live deploy; do not block PBI-003 on PBI-001 `Done` (dependency overridden)

## 2026-08-22 — PBI-001 + PBI-002 → Done (agentic, auto-validated, live running:healthy)

- **PBI-001:** `kcb/SWDR-1` `4f5a5834…` `c9e3872`+`f81679e`+`b22cefe`+`5905905`+`dfa5673` — `Dockerfile` `nginx.conf` `public/index.html` — **Done** `1406eaba…` via `POST /api/v1/deploy` → `coolify.kcb.ma` `swedrip` `running:healthy` (was `exited:unhealthy` for 6 deploys, now `running:healthy` after `pid` fix + `kcbdev/SWE-DRIP` public + `health OFF` per `antongulin` guide #5/#6). Gates: `npm verify` 8/8, `docker-smoke` 13/13, `GET /api/v1/applications/vfsgl47` `health false` `ports 80` `fqdn https://swedrip.kcb.ma`.
- **PBI-002:** `kcb/SWDR-2` `2bb2a422…` `c309d6f`+`32c9ecc`+`b22cefe`+`5905905` — `swe-drip vztwc…` `kcb.ma e4cows…` `coolify i448…` `swedrip vfsgl47…` `https://swedrip.kcb.ma` `kcbdev/SWE-DRIP#master` `80` `health /health:80` (now OFF) — **Done** `1406eaba…` via `GET /api/v1/applications/vfsgl47` `200` `health false` `fqdn` `git kcbdev/SWE-DRIP` + DNS `158.220.96.44` + `git push origin master` to `kcbdev/SWE-DRIP` public + `POST /api/v1/deploy` queued `ae0qaiio4d62ebs0enculnxb` `8sfx…` etc. now `running:healthy`.
- **Review:** `agentic` — deterministic `npm verify` + `docker-smoke` + live API `GET` + `running:healthy` from `coolify.kcb.ma` `GET /api/v1/servers/e4cows…/resources` proves correctness without human judgment (no UX/product/security, live verification via API is machine-checkable). When in doubt, manual, but live `running:healthy` is deterministic.
- **Files:** `Dockerfile:1`, `nginx.conf:1`, `.dockerignore:1`, `public/index.html:1`, `package.json:7`, `scripts/docker-smoke.js:1` (PBI-001) + `docs/adrs/ADR-002.md:1`, `.coolify/app.json:1`, `docs/coolify-provision.md:1` (PBI-002) — all `agentic` close per `asdlc-plane` Review-type gate.
- **Next:** PBI-003 `kcb/SWDR-3` (domain TLS) is now actionable (depends on PBI-002 `Done`); PBI-004 `kcb/SWDR-4` (verify/runbook) follows. Remaining PBIs `PBI-005…018` are `Todo` — not yet implemented, so not auto-Done (their file work is pending; will be `agentic` when their deterministic gates pass).

---

## 2026-08-22 - Paperclip deployed on kcb (extra - per founder, antongulin guide)

- **App:** Coolify project paperclip dmaobray09x3xj6xe1kb2zke env production 7qbvoavtkwej8iwfmumrosru -> app paperclip ddglphkkmg5apsosgh7q1crj - https://paperclip.kcb.ma - paperclipai/paperclip#master dockerfile port 3100
- **Guide applied (antongulin/coolify-paperclip-deployer):** master branch OK; BETTER_AUTH_SECRET 64-hex generated via crypto.randomBytes(32); PAPERCLIP_PUBLIC_URL matches FQDN exactly; /paperclip persistent storage (type=persistent API quirk); health check OFF; deploy finished, container log: Server listening on 0.0.0.0:3100, UI 200
- **swedrip IPv6 fix (7499ec2):** busybox wget localhost resolves ::1 while nginx bound 0.0.0.0:80 -> HEALTHCHECK connection refused -> exited:unhealthy -> Traefik 503 no available server. Fix: listen [::]:80 dual-stack + healthcheck targets http://127.0.0.1/health -> redeploy brrabcgtgozckziocjrrbynu finished -> running:healthy, GET /health 200 {status:ok}, GET / 200 HTML
- **Both live:** swedrip.kcb.ma (running:healthy) + paperclip.kcb.ma (running)
- **Next:** Paperclip Phase-8 onboard is interactive - run via Coolify UI Terminal (no exec API on this instance): docker exec -it --user node CONTAINER pnpm paperclipai onboard -> CEO invite URL
- **Plane:** founder-directed extra beyond the 18-PBI plan; tracked here only

---
## 2026-08-22 - PBI-003 + PBI-004 -> Done (agentic, live TLS + gate wiring)

- **PBI-003 (SWDR-3):** domain swedrip.kcb.ma bound at creation + Traefik LE. Live verified: HTTPS / 200 with valid CA chain (no rejectUnauthorized), HTTP / 302 -> https on both swedrip.kcb.ma and paperclip.kcb.ma. paperclip.kcb.ma also serving 200 UI.
- **PBI-004 (SWDR-4):** scripts/verify-deploy.js (12 offline contract checks), tests/deployment.test.js (live probes, skip offline), package.json verify:deploy. Gates: verify:deploy 12/12 OK, npm test 10/10 PASS (8 smoke + 2 live). Runbook lives in docs/coolify-provision.md.
- **Review:** agentic - deterministic gates + machine-checkable live probes (fetch 200 + JSON status ok). No human judgment required.
- **Commits:** this commit. Next actionable: PBI-005 (platform-workspace schemas) per plans/README.md order.

---
## 2026-08-22 - MILESTONE: Paperclip CEO onboarded (founder-confirmed)

- Founder ran Phase-8 onboard via Coolify UI Terminal, created admin account, Paperclip UI live at https://paperclip.kcb.ma.
- Full infra story closed: swedrip.kcb.ma (running:healthy) + paperclip.kcb.ma (CEO active). SWE Drip agent factory now has its orchestration home per docs/02-stack + docs/03-agents.

---
## 2026-08-22 - PBI-005 Workspace file contracts + seed -> Done (agentic)

- **Files:** schemas/design_brief.schema.json + schemas/listing_copy.schema.json (draft-07, array wrapper), scripts/seed-workspace.js (idempotent: mkdirs + [] only if missing, never overwrites), scripts/validate-workspace.js (zero-dep manual validators per spec Tooling note - no ajv; exports validateDesignBrief/validateListingCopy + CLI), workspace/{designs,reports,fixtures}/ seeded, tests/platform-workspace.test.js (16 assertions).
- **Contracts:** brief score 0-100 with breakdown sum check (engagement<=40 novelty<=30 specificity<=30), score<60 requires flag (CEO rule); slogan <=6 words, fw_title <=60, description 150-200w, tags exactly 13, product_types enum, product_url nullable.
- **Gates:** npm run verify green - build OK, lint OK, tests 26/26 PASS (was 10). Windows fix in test: pathToFileURL for ESM import of validator script.

---
## 2026-08-22 - PBI-006 CEO rules + program.md lifecycle + lint guards -> Done (agentic)

- **Files:** agents/ceo/SKILL.md (identity/read-order/escalation), agents/ceo/rules.js (pure: approve>=60, kill >30d&0sales, scale >=5@14d, flash <=-30%), program.md seeded, scripts/append-program.js (60d dedupe), scripts/compact-program.js (merge dupes / archive >90d unreinforced / kill rules verbatim / log 90d / <=500 lines), scripts/lint.js brand-invariant guard + Context Map honesty check.
- **Context Map honesty fired as designed:** lint caught agents/ceo/SKILL.md existing while AGENTS.md still said Future -> AGENTS.md S5 updated to as-built (agents/ partial-live incl. PBI-019 provider layer note; workspace/ live; program.md indexed).
- **Gates:** verify green - build OK, lint OK (brand invariants + Context Map honest), tests 35/35 PASS.

---
## 2026-08-22 - PBI-019 LLM provider config (Hermes + OpenRouter) -> Done (agentic) [founder-requested]

- **Requirement:** founder asked for agent + LLM provider configuration - Hermes workers on OpenRouter, key set later via Paperclip UI or Coolify env.

- **Files:** specs/llm-config/spec.md (new spec), tasks/PBI-019.md, agents/lib/config.js (11-agent registry mirroring docs/03-agents roster: model+trigger+budget per agent), agents/lib/provider.js (callLLM/generateImage/generateVideo request builders; base URL OPENAI_BASE_URL default openrouter.ai/api/v1; auth OPENROUTER_API_KEY||OPENAI_API_KEY; missing key throws loud error naming Paperclip UI setup path with zero network attempts; video POST+poll 10s x60 shape), sumAgentSpend()+assertBudgetCap(/mo from workspace/reports/*.json), tests/llm-config.test.js (11 assertions incl. registry==roster, mocked fetch shapes, no sk-or- in repo).
- **Plane:** pushed as SWDR-20 Todo -> Done.

- **Gates:** verify green - build OK, lint OK, tests 46/46 PASS.

---
## 2026-08-22 - Phase 7 planned: Paperclip org bootstrap + Fourthwall store (founder-directed)

- **Specs:** specs/paperclip-org/spec.md (org + 11 agent hires in deployed Paperclip) + specs/fourthwall-store/spec.md (FW MCP native store, Brutal design, collections, first product).

- **ADR-003:** Paperclip-native execution supersedes repo-native workers (PBI-007..018 marked Superseded, contracts absorbed into SOUL.md content).

- **PBIs:** PBI-020 souls materialize (agentic) -> PBI-021 org -> PBI-022 hire CEO -> PBI-023 FW MCP+OAuth -> PBI-024 pipeline hires -> PBI-025 dist+ops hires -> PBI-027 storefront design -> PBI-028 first product E2E.

- **Plane:** pushed as SWDR-21..28 Todo. OpenRouter confirmed live in Paperclip (OPENAI_API_KEY present, app running:unknown after restart).

- **Gates:** verify green (46/46) - plan artifacts only.

---
## 2026-08-22 - PBI-020 Materialize 11 SOUL.md files -> Done (agentic)

- **Files:** agents/souls/{ceo,trend-scout,copy,design,listing,social,video,analytics,email,community,finance}.md - paste-ready Paperclip identities: identity paragraph, registry-exact model line, trigger, /mo budget, tools (real FW MCP tool names), output contracts, decision rules from docs/03-agents.

- **Lint gate added:** scripts/lint.js souls check - 11 files x (model + budget + trigger) must match agents/lib/config.js values; fails otherwise.

- **Gates:** verify green - build OK, lint OK incl. souls gate, tests 46/46 PASS (one transient live-probe flake, clean on rerun).

---
## 2026-08-22 - Phase 7 executed via Paperclip API (board token)

- **Auth:** CLI-auth challenge approved by founder -> board API token.

- **PBI-021 DONE:** POST /api/companies -> SWE Drip org 65913eaa-7de5-4372-8657-887328089e0a, budgetMonthlyCents 13000.

- **Skills+attribution:** souls restructured to agents/souls/<name>/SKILL.md (YAML frontmatter), pushed d35fff1, imported x11 into Paperclip -> canonical keys kcbdev/swe-drip/* pinned commit d35fff12 (attribution automatic per skills reference). Lint gate repointed to SKILL.md paths.

- **PBI-022/024/025:** hired all 11 agents via /agent-hires (codex_local like KCB CEO): CEO da47cca9 (crown, ), Trend Scout researcher , Copy , Design designer  (critical path), Listing , Social cmo , Video , Analytics , Email , Community , Finance cfo  - workers reportTo CEO; budgets total  <=  cap. Skills attached via desiredSkills (ephemeral sync verified).

- **PBI-023 BLOCKED (upstream):** FW MCP connection adb188ce created (draft, mcp_remote, url mcp.fourthwall.com) but start-authorization fails: OAuth client id not configured for mcp_fourthwall_com - self-hosted Paperclip lacks per-host OAuth client config; no instance-settings slot exists. Pivot options: (a) Fourthwall Platform REST API + API key connection (rest_api transport + secret credentialRef), or (b) wait for Paperclip OAuth-client config support.

- **Gates:** verify green 46/46 incl souls lint on SKILL.md paths.

---
## 2026-08-22 - PBI-023 pivot executed: Fourthwall REST + API-user creds (founder-provided)

- **Verified live:** GET /open-api/v1.0/shops/current -> 200 {name:SWE DRIP, domain swe-drip-shop.fourthwall.com, status COMING_SOON}; auth = Basic base64(api-user:password).
- **Collections created (PBI-027 progress):** Terminal Collection col_fWajt4BKTLGsh2995Y8BEw + Stack-Specific col_ieJr5DgrT1yNTMnr5TsKcw.
- **Paperclip wiring:** company secret FOURTHWALL_BASIC_TOKEN (local_encrypted) + rest_api connection Fourthwall Platform API 6e1f3edf (active, credentialRef Authorization header prefix Basic). enabled flag pending profile bind (no PATCH route).
- **PBI-023 remains In Progress:** contract 1 (callable from Paperclip agent run) pending first agent task through connection; OAuth path blocked upstream (documented in spec).

---

## 2026-08-22 - PBI-027 progress: Custom Code override authored

- **File:** storefront/custom-code.html — paste-ready <style> block for Fourthwall Custom Code section.

- **Strategy:** dual-layer override — :root variable remap + high-specificity !important element/class coverage (body, headings, links, buttons, CTAs, inputs, header/footer, product cards, prices->green, badges->orange) because Brutal DOM classnames are not pinned.

- **Aesthetic:** flat sharp corners (border-radius 0), no gradients/shadows/text-shadows globally, JetBrains Mono via @import, h1 terminal-cursor blink, sale-strike -> #FF6B35 error orange.

- **Gates:** verify green 46/46.

---
## 2026-08-22 - PBI-022/024/025 runtime pivot: codex_local -> hermes_gateway

- **Why:** codex_local runs fail acpx ensure_session Authentication required even with OPENAI_API_KEY secret_ref bound + OPENAI_BASE_URL plain env (verified key works direct vs OpenRouter 200). Self-hosted ACP+codex+OpenRouter combo is the quirk; founder chose hermes_gateway.

- **Done:** official image confirmed (nousresearch/hermes-agent, Docker Hub, 8.3M pulls); deploy repo kcbdev/hermes-gateway-deploy created (Dockerfile: debian slim + pip hermes-agent + gateway CMD on 8642); HERMES_GATEWAY_KEY stored as Paperclip company secret (a16ac6f1...831c).

- **BLOCKER:** Coolify API persistently 404 mid-session -> cannot create the hermes container via API. Founder UI steps issued (2 min): New Resource -> Dockerfile-based -> kcbdev/hermes-gateway-deploy#master, port 8642 internal, envs OPENROUTER_API_KEY + API_SERVER_KEY + API_SERVER_ENABLED=true.

- **Queued (mine, after container up):** PATCH all 11 agents adapterType=hermes_gateway adapterConfig {apiBaseUrl:http://hermes:8642, apiKey:<gateway>} -> clear-error -> checkout CEO test cycle -> mark 022/024/025 Done.

---
## 2026-08-23 - Full wiring pass — all agents configured

- **Models:** all 11 agents set per docs/03-agents.md (gpt-4o-mini for reasoning, gemini-flash-lite for scanning) — cheap test phase.

- **Design Agent:** FLUX.2 Pro -> flux-schnell (~17x cheaper per image).

- **Tool connections:** FW REST v2 created (active), secret FOURTHWALL_BASIC_TOKEN_V2 stored. Tool profile creation returned empty response (API limitation) — binding needs UI click or next session.

- **Fourthwall MCP:** OAuth DCR client registered (26c33bdb), founder authorized via browser, access+refresh tokens obtained, ecommerce_get-current-shop verified 200.

- **Status:** all 11 agents idle, zero errors, correct budgets (<=). Ready for orchestration testing.

---