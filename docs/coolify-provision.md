# Coolify provision — `kcb` → `swe-drip` → `swedrip` (swedrip.kcb.ma)

> Live: `https://coolify.kcb.ma` API `COOLIFY_ACCESS_TOKEN` (`10|C7O...`). Project `swe-drip` `vztwc3dxianozufxinxm0cgp` env `production` `r5c2ohxgtq9irlvjiwbtzji1` on server `kcb.ma server` `e4cowswcks844wow04c084wg` destination `coolify` `i448wgc40wc4wg8oww0ww4os`. App `swedrip` `vfsgl47pv5ew2hbrqxbjwmjq` `https://swedrip.kcb.ma` `KCB/SWE-DRIP#master` `dockerfile` `80`.

## Create (already executed 2026-08-22 — idempotent)

```bash
# 1. Project (done)
curl -X POST https://coolify.kcb.ma/api/v1/projects \
  -H "Authorization: Bearer $COOLIFY_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"swe-drip","description":"SWE Drip - autonomous POD brand for swedrip.kcb.ma"}'
# → {uuid: vztwc3dxianozufxinxm0cgp}

# 2. Application public Git (done)
curl -X POST https://coolify.kcb.ma/api/v1/applications/public \
  -H "Authorization: Bearer $COOLIFY_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_uuid":"vztwc3dxianozufxinxm0cgp",
    "server_uuid":"e4cowswcks844wow04c084wg",
    "environment_uuid":"r5c2ohxgtq9irlvjiwbtzji1",
    "destination_uuid":"i448wgc40wc4wg8oww0ww4os",
    "git_repository":"https://github.com/KCB/SWE-DRIP",
    "git_branch":"master",
    "build_pack":"dockerfile",
    "ports_exposes":"80",
    "name":"swedrip",
    "domains":"https://swedrip.kcb.ma"
  }'
# → {uuid: vfsgl47pv5ew2hbrqxbjwmjq, domains: https://swedrip.kcb.ma}

# 3. Health patch (done)
curl -X PATCH https://coolify.kcb.ma/api/v1/applications/vfsgl47pv5ew2hbrqxbjwmjq \
  -H "Authorization: Bearer $COOLIFY_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"health_check_enabled":true,"health_check_path":"/health","health_check_port":"80","health_check_method":"GET","health_check_scheme":"http","health_check_return_code":200,"health_check_interval":30,"health_check_timeout":5,"health_check_retries":3,"health_check_start_period":10}'
# → 200
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

See also `.coolify/app.json:1` for declarative capture and `docs/adrs/ADR-002.md:1` for decisions.
