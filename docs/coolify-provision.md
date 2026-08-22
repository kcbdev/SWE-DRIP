# Coolify provision — `kcb` → `swe-drip` → `swedrip` (swedrip.kcb.ma)

> Live: `https://coolify.kcb.ma` API `COOLIFY_ACCESS_TOKEN` (`10|C7O...`). Project `swe-drip` `vztwc3dxianozufxinxm0cgp` env `production` `r5c2ohxgtq9irlvjiwbtzji1` on server `kcb.ma server` `e4cowswcks844wow04c084wg` destination `coolify` `i448wgc40wc4wg8oww0ww4os`. App `swedrip` `vfsgl47pv5ew2hbrqxbjwmjq` `https://swedrip.kcb.ma` `kcbdev/SWE-DRIP#master` `dockerfile` `8080` (non-root, was 80).

## Create (already executed 2026-08-22 — idempotent)

```bash
# 1. Project (done)
curl -X POST https://coolify.kcb.ma/api/v1/projects \
  -H "Authorization: Bearer $COOLIFY_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"swe-drip","description":"SWE Drip - autonomous POD brand for swedrip.kcb.ma"}'
# → {uuid: vztwc3dxianozufxinxm0cgp}

# 2. Application public Git (done — corrected to kcbdev/SWE-DRIP after git push)
curl -X POST https://coolify.kcb.ma/api/v1/applications/public \
  -H "Authorization: Bearer $COOLIFY_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_uuid":"vztwc3dxianozufxinxm0cgp",
    "server_uuid":"e4cowswcks844wow04c084wg",
    "environment_uuid":"r5c2ohxgtq9irlvjiwbtzji1",
    "destination_uuid":"i448wgc40wc4wg8oww0ww4os",
    "git_repository":"kcbdev/SWE-DRIP",
    "git_branch":"master",
    "build_pack":"dockerfile",
    "ports_exposes":"8080",
    "name":"swedrip",
    "domains":"https://swedrip.kcb.ma"
  }'
# → {uuid: vfsgl47pv5ew2hbrqxbjwmjq, domains: https://swedrip.kcb.ma}
# Patched 2026-08-22: PATCH /api/v1/applications/vfsgl47… → git_repository https://github.com/kcbdev/SWE-DRIP (was KCB/SWE-DRIP, repo 404) after git push to kcbdev/SWE-DRIP master succeeded

# 3. Health patch (done — updated 2026-08-22 to 8080 for USER nginx non-root)
curl -X PATCH https://coolify.kcb.ma/api/v1/applications/vfsgl47pv5ew2hbrqxbjwmjq \
  -H "Authorization: Bearer $COOLIFY_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"health_check_enabled":true,"health_check_path":"/health","health_check_port":"8080","health_check_method":"GET","health_check_scheme":"http","health_check_return_code":200,"health_check_interval":30,"health_check_timeout":5,"health_check_retries":3,"health_check_start_period":10, "ports_exposes":"8080"}'
# → 200 (was 80, changed to 8080 for non-root; Traefik still terminates TLS and routes to 8080)
```

## Verify

```bash
curl -H "Authorization: Bearer $COOLIFY_ACCESS_TOKEN" https://coolify.kcb.ma/api/v1/applications/vfsgl47pv5ew2hbrqxbjwmjq | jq '.health_check_enabled, .health_check_path, .fqdn, .git_repository'
# → true "/health" "https://swedrip.kcb.ma" "KCB/SWE-DRIP"

curl -H "Authorization: Bearer $COOLIFY_ACCESS_TOKEN" https://coolify.kcb.ma/api/v1/projects/vztwc3dxianozufxinxm0cgp | jq .name
# → "swe-drip"
```

## Env vars (Coolify UI → swe-drip → swedrip → Environment Variables — mark Secret where noted)

```
OPENROUTER_API_KEY / OPENAI_API_KEY (Secret) — same value
OPENAI_BASE_URL=https://openrouter.ai/api/v1
DEFAULT_MODEL=anthropic/claude-sonnet-4-6
WORKSPACE_PATH=/workspace
FOURTHWALL_MCP_TOKEN (Secret)
TELEGRAM_BOT_TOKEN (Secret)
TELEGRAM_CHAT_ID (Secret)
LOOPS_API_KEY (Secret)
BUFFER_ACCESS_TOKEN (Secret)
```

All are Runtime variables (not Build Variable) — default in Coolify.

## Storages (future — Paperclip)

Not attached in this PBI. Reserved names: `paperclip-data:/app/data`, `paperclip-workspace:/workspace` (see `.coolify/app.json` `volumes.future`). Attach in `Coolify → swedrip → Storages` when Paperclip PBI lands — names identical so no rename.

## Deploy

```bash
# Requires git push of local master (c9e3872 etc.) to https://github.com/KCB/SWE-DRIP#master first
# (repo currently 404 — create via GitHub UI or `gh repo create KCB/SWE-DRIP --public --source=. --push`)
curl -X POST https://coolify.kcb.ma/api/v1/applications/vfsgl47pv5ew2hbrqxbjwmjq/deploy \
  -H "Authorization: Bearer $COOLIFY_ACCESS_TOKEN"
# Or UI: Coolify → swe-drip → swedrip → Deploy
# Build log should show: FROM node:22-alpine → npm run build/lint/test → FROM nginx:alpine → nginx -t → HEALTHCHECK
```

After deploy: `GET https://swedrip.kcb.ma/health` → `{"status":"ok"}` (TLS is PBI-003 verification — expected 200 with LE cert after `http→301` to `https`).

## Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| `kcbdev/SWE-DRIP` not found on deploy | No `git push` of `master` to `KCB/SWE-DRIP` yet (404) | `git remote add origin https://github.com/KCB/SWE-DRIP.git && git push -u origin master` (or create repo via `gh repo create KCB/SWE-DRIP --public`) |
| Health `exited:unhealthy` | `HEALTHCHECK` fails (nginx not serving `/health`) | Verify `nginx.conf` `location = /health` + `Dockerfile` `HEALTHCHECK` `wget -qO- http://localhost/health` |
| `domains` not reachable | DNS `swedrip.kcb.ma` → `158.220.96.44` ok via wildcard `*.kcb.ma` → `kcb` server; if 404 check Traefik route `Host(\`swedrip.kcb.ma\`)` in `GET /api/v1/applications/vfsgl…` `fqdn` |
| Env missing | Not set in Coolify UI | Set in `Environment Variables` tab, mark Secret, redeploy |

## Paperclip (deployed 2026-08-22 — per antongulin/coolify-paperclip-deployer)

Project `paperclip dmaobray09x3xj6xe1kb2zke` env `production 7qbvoavtkwej8iwfmumrosru` → app `paperclip ddglphkkmg5apsosgh7q1crj` — `https://paperclip.kcb.ma` — `paperclipai/paperclip#master` dockerfile port `3100` health **OFF** (guide #6), storage `persistent ddglph…-paperclip-data → /paperclip`, envs: `HOST=0.0.0.0`, `PAPERCLIP_HOME=/paperclip`, `PAPERCLIP_PUBLIC_URL=https://paperclip.kcb.ma` (matches FQDN exactly, guide #3), `BETTER_AUTH_SECRET=<64-hex>`, `PAPERCLIP_ALLOWED_HOSTNAMES=paperclip.kcb.ma`, `PAPERCLIP_TELEMETRY_DISABLED=1`.

**Live:** container log `Server listening on 0.0.0.0:3100`; UI returns 200.

**Onboard (Phase 8 — interactive, run via Coolify UI → paperclip → Terminal, no exec API on this instance):**
```bash
docker exec -it --user node $(docker ps -q --filter "publish=3100") pnpm paperclipai onboard
# Quickstart → say NO to "start now" (already running) → copy CEO invite URL → open in browser
```

## Deployed state (verified live 2026-08-22)

| App | URL | Status | Proof |
|---|---|---|---|
| swedrip | https://swedrip.kcb.ma | running:healthy | `GET /health` → 200 `{"status":"ok"}`, `GET /` → 200 HTML |
| paperclip | https://paperclip.kcb.ma | running | `GET /` → 200 Paperclip UI; `Server listening on 0.0.0.0:3100` |

**IPv6 gotcha (swedrip):** Alpine busybox `wget localhost` resolves `::1` first; nginx bound only `0.0.0.0:80` → Docker HEALTHCHECK connection-refused → rollback → `exited:unhealthy` → Traefik `503 no available server`. Fix: `listen [::]:80;` dual-stack + healthcheck targets `http://127.0.0.1/health`.

See also `.coolify/app.json:1` for declarative capture and `docs/adrs/ADR-002.md:1` for decisions.
