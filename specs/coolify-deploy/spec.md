# Spec: Coolify Deploy — SWE Drip on kcb (swedrip.kcb.ma)

## Goal

Deploy SWE Drip (currently docs-only + verification harness) to the existing Coolify instance on server `kcb` and expose it at `https://swedrip.kcb.ma` with zero-downtime, auto-renewing TLS, health-checked container, and runnable deterministic gates. The deployment is the durable path for all future PBIs — `asdlc-execute` ships through it.

## Scope

- In scope:
  - Container image for the repo (multi-stage Dockerfile, nginx serving static docs + health endpoint, non-root, slim base)
  - Compose / Coolify application definition for server `kcb`, domain `swedrip.kcb.ma`, persistent volumes where needed, env-var injection for secrets, health check
  - Domain + Traefik TLS via Coolify (Let's Encrypt auto-renew, https redirect, HSTS where possible)
  - Deployment verification harness (local docker build/run, `curl https://swedrip.kcb.ma/health` → 200, `npm run verify` still green, smoke tests cover deployed artifact)
  - ADR + runbook for redeploy/rollback, env-var rotation, and volume backup per `docs/04-deploy.md`
- Out of scope:
  - Provisioning Hetzner VPS `kcb` itself (exists), or creating a new Plane project
  - DNS zone creation (assumes `kcb.ma` zone exists and owner can add `swedrip` CNAME/A → Coolify IP)
  - Full Paperclip 10-agent runtime (described in `docs/03-agents.md`; this spec deploys the repo artifact, not the Paperclip volume set — Paperclip volumes `paperclip-data`/`paperclip-workspace` are documented as future, not required to ship this spec)
  - Paid traffic / Fourthwall storefront secrets — env names documented, values remain in Coolify secrets UI
  - Migrating legacy history (none; onboarding was root commit `6420ca1`)

## Contracts (success criteria)

All are independently verifiable; a PBI is not "done" until its contract's check passes.

1. **Container builds locally without network hacks**
   - `docker build -t swedrip:local .` succeeds from clean checkout, no cached layers required, image < 50 MB compressed, runs as non-root, exposes `3000` (or `80` behind nginx) and serves static docs.

2. **Coolify application exists on server `kcb` and tracks this repo**
   - In Coolify UI `kcb` → project `swe-drip` (or equivalent) → application `swedrip` is present, type `Dockerfile` (or `Docker Image` if registry mode), connected to git `KCB/SWE-DRIP` `master`, server = `kcb`, port = app's exposed port, health check path `/health`, restart policy on-failure, resource limits left at Coolify defaults unless PBI overrides.

3. **Domain `swedrip.kcb.ma` serves over https with auto TLS**
   - `https://swedrip.kcb.ma/` returns 200 (not 301 loop), presents a valid Let's Encrypt cert for `swedrip.kcb.ma` (not self-signed), `http://swedrip.kcb.ma/` redirects 301→https, `curl -Ik https://swedrip.kcb.ma/` shows `strict-transport-security` if Traefik HSTS enabled.

4. **Health endpoint is deterministic and gates still pass**
   - `GET https://swedrip.kcb.ma/health` → 200 `{"status":"ok"}` (or static `health` file equivalent), latency < 500 ms from MA/EU, and local `npm run verify` (build + `node scripts/lint.js` + `node --test tests/*.test.js` — 8/8) remains green after deployment changes. No PBI may leave `Active` red.

5. **Secrets and env-vars are not baked into the image**
   - `docker history swedrip:local --no-trunc | grep -i -E "OPENROUTER|FOURTHWALL|TELEGRAM|PLANE_API"` returns 0 hits; Coolify env-vars are marked `Secret` where required per `docs/02-stack.md`; redeploy preserves them (no "build variable" unless explicitly documented).

6. **Redeploy and rollback are documented and one-click**
   - Runbook in `docs/adrs/` or `docs/04-deploy.md` delta lists: `Coolify → swedrip → Redeploy` (preserves volumes/env), `Rollback` via Coolify's previous image, and `docker logs` location. A second deploy within 10 min without manual SSH succeeds.

## Anti-patterns

- Do not hardcode secrets, tokens, or certs in `Dockerfile`, compose, or markdown — only placeholder var names.
- Do not run as `root` inside the container, do not expose Docker socket to the app.
- Do not add a second deployment target (Vercel/Netlify/railway) — this spec is Coolify-only on `kcb`.
- Do not claim Hetzner provisioning in the deploy gate — `kcb` is pre-existing.
- Do not swallow `AGENTS.md` plane binding: any doc that mentions Plane must still say `kcb/SWDR (2af62f36-c11a-411a-89b5-8e5a5176b829)`.
- Do not invent a new verification runner — gates remain `npm run build` / `npm run lint` / `npm test` (node:test).
- Do not mark the spec done while `npm run verify` is red, even if the site is live (Ralph Loop gate is mandatory).

## Decisions

- **Decision-1 — Static nginx over Next.js for this spec:** repo has no app code; serving docs as static placeholder keeps image < 50 MB and deploys without Paperclip dependency. Future PBIs can swap to Node SSR without changing the Coolify plumbing. → ADR-002.
- **Decision-2 — Coolify deployment via UI + API duality:** primary path is Coolify UI on `kcb` (as in `docs/04-deploy.md` Day 1), with Coolify MCP/API (`freqkflag/coolify-mcp-server`) as optional automation — do not require MCP for gate 3, but document the API shape where it helps.
- **Decision-3 — Reuse `docs/04-deploy.md` topology:** Hetzner CX31 → Coolify `:8000`/`:443` → Traefik → `swedrip` app `:3000` → volumes `/app/data`, `/workspace` reserved names (future Paperclip volumes are named identically so a later PBI can attach without rename).
- **Decision-4 — Domain `swedrip.kcb.ma` via Coolify Domains tab:** add as `https://swedrip.kcb.ma`, let Traefik + Let's Encrypt issue; do not run custom certbot or Nginx outside Coolify.

## Tooling (capability discovery)

Gaps extracted from plan: containerize, Coolify API, TLS, deployment pipeline design.

| Skill (candidate) | What it does | Installs | Source | Verdict |
|---|---|---|---|---|
| `ajmcclary/coolify-manager@coolify-manager` | Coolify API/MCP wrapper — create/manage apps, env, deployments | 435 | ajmcclary | **Adopt** — Coolify ops on `kcb` |
| `oakoss/agent-skills@coolify` | Coolify deployment recipes + health checks | 282 | oakoss | Alternative — pick one of top-two after probe |
| `v1truv1us/ai-eng-system@coolify-deploy` | Coolify deploy pipeline template | 177 | v1truv1us | Consider if it adds compose generator |
| `wshobson/agents@deployment-pipeline-design` | Pipeline design (CI → build → deploy → verify) | 11.7K | wshobson | **Adopt** — gate plan + verification stages |
| `affaan-m/ecc@docker-patterns` | Production Dockerfile patterns (multi-stage, non-root, slim) | 10.5K | affaan-m | **Adopt** — guides PBI-001 |
| `github/awesome-copilot@multi-stage-dockerfile` | Multi-stage Dockerfile best practices | 21.5K | github (official) | **Adopt** — cross-check with docker-patterns |
| `manutej/luxor-claude-marketplace@docker-compose-orchestration` | Compose orchestration + volumes + healthchecks | 2.6K | manutej | Optional — only if compose mode chosen over plain Dockerfile |

> Skills are **candidates** — none auto-installed. Approval below gates installation via `cmd /c "skills add <owner/repo> --skill <name> -g -a opencode --copy"`. Records updated in `plans/README.md` Gate plan after adoption.

## Open questions (need founder before closing spec)

- Q1: Coolify access — does the founder already have admin on `kcb` at `:8000`, or is `kcb` SSH-only and Coolify needs install (`curl https://cdn.coollabs.io/coolify/install.sh`) per `docs/04-deploy.md:1.2`?
- Q2: DNS — is `swedrip.kcb.ma` already CNAME → `kcb` IP, or should PBI-003 include the DNS record step (Route53/Cloudflare)?
- Q3: Registry vs Git-direct — should Coolify build from `KCB/SWE-DRIP` GitHub (preferred, no registry secret) or pull `paperclipai/paperclip` style Docker Image mode?
- Q4: Paperclip volumes — reserve empty named volumes `paperclip-data`/`paperclip-workspace` now (no mount yet, just declared) to avoid future rename, or leave volumes undeclared until Paperclip PBI lands?
