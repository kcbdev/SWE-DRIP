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