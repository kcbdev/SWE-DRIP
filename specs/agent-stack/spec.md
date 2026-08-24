# Spec: Agent Stack — working Paperclip + Hermes + Postgres on Coolify

## Goal

Replace the non-functional Paperclip/Hermes topology with one **source-of-truth Docker Compose stack** (PostgreSQL + Paperclip-from-source + Hermes gateway) deployed as a single Coolify service in the `paperclip` project, so the 11-agent SWE Drip company runs autonomously with **persistent memory** (`/opt/data`), durable state (Postgres), and a first-class `hermes_gateway` connection. This spec corrects the five root causes documented in `plans/PROGRESS.md` (2026-08-24): nonexistent paperclip image, wrong Hermes data volume path, non-first-class gateway adapter + insecure-HTTP guard, OpenRouter 402 from 128k max_tokens, and cross-project/network fragmentation.

## Scope

- In scope:
  - `deploy/docker-compose.yml` — one compose, one private bridge network, three services:
    - `postgres` (`postgres:17-alpine`) with healthcheck + named volume `pgdata`
    - `paperclip` **built from `paperclipai/paperclip` source** (never `paperclipai/paperclip:latest` image — does not exist on Docker Hub), port 3100, named volume `paperclip-data:/paperclip`, env: `BETTER_AUTH_SECRET`, `PAPERCLIP_TOOL_ACTION_SIGNING_SECRET`, `PAPERCLIP_PUBLIC_URL=https://paperclip.kcb.ma`, `DATABASE_URL=postgres://paperclip:…@postgres:5432/paperclip`, OpenRouter keys as env placeholders
    - `hermes` (`nousresearch/hermes-agent:latest`) with `command: gateway run`, `API_SERVER_ENABLED=true`, `API_SERVER_KEY` (env placeholder), **volume `hermes-data:/opt/data`** (the memory path: config.yaml, sessions/, memories/, skills/, logs/), expose 8642 internal, `HERMES_DASHBOARD=0`, resource limits (memory 4G / cpus 2 / shm 1g)
  - `deploy/stack/hermes-config.yaml` — Hermes seed config: `provider: openrouter`, `max_tokens: 4096` (fixes OpenRouter 402), per-agent models per `docs/03-agents.md`
  - `scripts/lint.js` extension — compose sanity gate (no baked secrets, `/opt/data` not `/home/hermes`, paperclip built not pulled)
  - `tests/agent-stack.test.js` — offline contract checks for the compose/config
  - Runbook `docs/agent-stack-provision.md` — Coolify UI steps (REST create is unreliable)
  - 11 agents rewired in Paperclip to `hermes_gateway` adapter (`apiBaseUrl http://hermes:8642`, `apiKey` = Hermes `API_SERVER_KEY` as secret, `dangerouslyAllowInsecureRemoteHttp: true` for docker-internal HTTP, `sessionKeyStrategy: issue`, `persistSession: false` until #1160 confirmed fixed)
- Out of scope:
  - Repo-native worker execution (PBI-007..018 remain superseded — contracts live in SOUL.md)
  - Fourthwall product-creation upload fix (separate spec `specs/fourthwall-store/spec.md`; PBI-036)
  - OpenRouter key management (founder-owned; env placeholders only)
  - Removing the old paperclip app / old hermes service containers (stopped as backup; deletion is a founder decision)

## Contracts (success criteria)

1. **Compose parses and is deployable** — `docker compose -f deploy/docker-compose.yml config` succeeds (when docker available); lint gate passes; no `sk-or-`/hex API keys appear in any tracked compose/config file (env placeholders only).
2. **Hermes memory path is correct** — hermes service mounts `hermes-data:/opt/data` (not `/home/hermes/.hermes`); lint enforces this; `hermes-config.yaml` sets `max_tokens: 4096` and `provider: openrouter`.
3. **Paperclip is built, not pulled** — paperclip service uses `build:` context from `paperclipai/paperclip` source; no `image: paperclipai/paperclip:latest` anywhere; lint enforces.
4. **Provisioned on Coolify** — single service in project `paperclip` (dmaobray…) running: `https://paperclip.kcb.ma/api/health` → 200; `docker exec <hermes> hermes --version` → ≥ 0.20.5; hermes `/api/health` reachable on internal network; postgres healthy.
5. **Agents wired to gateway** — all 11 agents use `hermes_gateway` with `apiBaseUrl http://hermes:8642` + `API_SERVER_KEY` secret; `testEnvironment` returns reachable; CEO decision-cycle task returns a **non-empty transcript with tool calls and recorded cost**.
6. **Memory persists across restart** — after `control restart` of the hermes container, a second CEO cycle recalls prior session/memory context from `/opt/data`; skills list still populated.

## Anti-patterns

- Do not use `paperclipai/paperclip:latest` (image does not exist).
- Do not mount Hermes state at `/home/hermes/.hermes` — official image uses `/opt/data`.
- Do not bake any secret (API key, gateway key, Fourthwall token) into compose or config — env placeholders only.
- Do not run hermes-gateway agents against a non-loopback HTTP URL without `dangerouslyAllowInsecureRemoteHttp: true` (adapter blocks it otherwise).
- Do not enable `persistSession: true` before Paperclip issue #1160 regex fix is confirmed (infinite no-op runs).
- Do not exceed Hermes `max_tokens: 128000` against the low-credit OpenRouter key (402) — cap at 4096.
- Do not add a fourth service or split the stack across Coolify projects/networks.

## Decisions

- **Decision-1 — One compose, one Coolify service, one network.** Supersedes the fragmented paperclip-app + hermes-service + second-project layout. Internal DNS (`hermes`, `paperclip`, `postgres`) resolves only inside the compose network. → ADR-004.
- **Decision-2 — `hermes_gateway` (first-class, Paperclip ≥ v2026.626.0) over manual hermes_local pip-install.** The official built-in adapter with secret-ref API key and session key strategy is the supported path; the in-container pip-install experiment is abandoned. → ADR-004.
- **Decision-3 — Provision via Coolify UI (Docker Compose resource), verify via Coolify MCP.** REST create endpoints are unreliable (404s); the MCP server has no create tool. The repo compose is the single source of truth; Coolify just points at it.

## As-built (2026-08-24, founder-directed "edit current resource paperclip")

**Decision-1 superseded in practice** — instead of a new single-compose service, the existing resources were **edited in place** (Coolify REST API confirmed working for existing resources):

- **Paperclip** = standalone app `ddglphkkmg5apsosgh7q1crj` (dockerfile build from `paperclipai/paperclip@master`, port 3100, fqdn paperclip.kcb.ma) — **running**, uses its **embedded DB** (no external postgres needed). `GET https://paperclip.kcb.ma/api/health` → 200.
- **Hermes** = service `kh85cuzhgfz1ib19x6d6es6i` (project `dmaobray…`, env production) — **edited**: volume corrected to `hermes-data:/opt/data` (was `/home/hermes/.hermes`), `command: gateway run` added, secrets moved from baked compose to Coolify-managed env (`OPENROUTER_API_KEY`, `API_SERVER_KEY`, `FOURTHWALL_AUTH`), `shm_size: 1g`. Gateway confirmed listening on 0.0.0.0:8642 under s6 supervision.
- Both resources are in the **same project + environment** → shared docker network (`kh85cuzhgfz1ib19x6d6es6i` for the service); Paperclip reaches Hermes at `http://hermes:8642`.
- **Stale orphan records** (swedrip-web app, paperclip app, postgres db in the service) are cosmetic only — no delete endpoint exposed via REST (404); they do not affect the running hermes container.
- Contract 4's "postgres healthy" is **not applicable** in the as-built (Paperclip embedded DB); contract's single-compose wording is superseded by this as-built note.

## As-built addendum — Hermes owns the model for gateway agents (2026-08-24, verified)

- For `hermes_gateway` agents, the **Paperclip per-agent `model` field is ignored by design** ("Hermes manages its own model" — upstream hermes_gateway docs). The actual model is whatever Hermes's own `config.yaml` specifies.
- **Observed failure:** with `model.default` unpinned, Hermes auto-resolves an expensive default (opus-class via OpenRouter) and rotates through fallback models (incl. GLM) — founder saw `opus` + `glm` in OpenRouter usage while Paperclip reported gateway runs as model `unknown`. This also amplified the 402 credit-exhaustion failures.
- **Corrective config (applied via founder SSH exec):** `model.default: openrouter/openai/gpt-4o-mini`, `model.provider: openrouter`, `model.max_tokens: 4096`, `approvals.mode: off`. Canonical file: `deploy/stack/hermes-config.yaml`. Per-agent model routing through gateway agents is therefore **not supported** — the global Hermes model applies to all gateway agents during the test phase.
- The 10 non-gateway agents (currently `hermes_local`) DO honor the Paperclip model field (passed via `--model` to the CLI) — those are set to the cheap test models (gpt-4o-mini / gemini-2.0-flash-lite-001).

## Tooling

- Coolify MCP (`https://coolify.kcb.ma/mcp`) — verify status, control restarts, read logs; no create.
- No new third-party skills — methodology and tooling already in repo.
