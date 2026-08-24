# SWE Drip — working agent stack (Postgres + Paperclip + Hermes gateway)

Single source of truth: `specs/agent-stack/spec.md`. One compose, one private
network, three services. Paperclip is **built from source** (the
`paperclipai/paperclip` Docker image does not exist); Hermes stores all state
(memory) at `/opt/data`.

## Architecture

```
agent-stack-net (bridge, one Coolify compose service)
├── postgres:17-alpine      :5432   volume pgdata         ← Paperclip DB
├── paperclip (build)       :3100   volume paperclip-data ← control plane + board
└── hermes gateway          :8642   volume hermes-data:/opt/data ← agent runtime + memory
```

- Paperclip (port 3100) is bound to `https://paperclip.kcb.ma` via Coolify/Traefik.
- Hermes exposes its gateway API on internal port 8642 (`API_SERVER_ENABLED=true`,
  `API_SERVER_KEY`). Paperclip agents connect with the `hermes_gateway` adapter at
  `http://hermes:8642` (same network — internal DNS only, not internet-exposed).
- Hermes memory (sessions, memories, skills) persists in `hermes-data` at `/opt/data`.

## Deploy on Coolify (PBI-033, UI)

1. Coolify → project **paperclip** → **+ New Resource** → **Docker Compose**.
2. Point at `kcbdev/SWE-DRIP` branch `master`, compose file `deploy/docker-compose.yml`.
3. Set env vars in the Coolify UI (never commit them):
   - `POSTGRES_PASSWORD` — strong password
   - `BETTER_AUTH_SECRET` — `openssl rand -hex 32`
   - `PAPERCLIP_TOOL_ACTION_SIGNING_SECRET` — `openssl rand -hex 32`
   - `OPENROUTER_API_KEY` — your sk-or-… key
   - `API_SERVER_KEY` — any 64-char hex (this is the Hermes gateway key Paperclip agents use)
4. Bind `https://paperclip.kcb.ma` to the paperclip service (port 3100).
5. Deploy. Wait for postgres healthy → paperclip up → hermes gateway listening on 8642.

## Post-boot config (PBI-035)

Inside the hermes container: `hermes config set provider openrouter` and
`hermes config set max_tokens 4096` (canonical file: `deploy/stack/hermes-config.yaml`).

## Wire agents (PBI-034)

All 11 agents → adapter `hermes_gateway`, `apiBaseUrl: http://hermes:8642`,
`apiKey` = `API_SERVER_KEY` (as a Paperclip company secret),
`dangerouslyAllowInsecureRemoteHttp: true`, `sessionKeyStrategy: issue`,
`persistSession: false` until Paperclip issue #1160 is confirmed fixed.
