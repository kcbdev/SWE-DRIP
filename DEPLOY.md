# SWE Drip — Coolify Deployment Guide

Commit `6d03124` pushed to `kcbdev/SWE-DRIP` main. Code is ready for deployment.

## What Was Done

- `Dockerfile.api` — Python 3.11 multi-stage build, uvicorn on port 8000
- `Dockerfile.panel` — Node 22 multi-stage build, Next.js standalone on port 3000
- CORS middleware on API (allows `swedrip-panel.kcb.ma` + `localhost:3000`)
- `output: "standalone"` enabled in `next.config.ts`
- All gates green: 101 frontend tests, 408 backend tests, parity OK

## Coolify Setup (Manual — MCP is read-only)

### Step 1: Create Project

1. Coolify UI → Projects → New Project
2. Name: `SWE DRIP`

### Step 2: Create PostgreSQL Database

1. Inside "SWE DRIP" project → New → Database
2. Type: `PostgreSQL`
3. Name: `swe-drip-db`
4. Version: `17` (with pgvector if available, otherwise standard 17)
5. Internal Host: **the database UUID shown in Coolify** (e.g. `ocbet4huqvytlcyoaoub19bk`).
   The friendly name `swe-drip-db` does **not** resolve on the `coolify` Docker
   network — using it produces `Temporary failure in name resolution` at runtime.
6. Port: `5432`
7. Database: `swe_drip`
8. User: `swe_drip`
9. Password: generate a strong one
10. Create and note the **internal connection string**:
    ```
    postgresql://swe_drip:<password>@<db-uuid>:5432/swe_drip
    ```

### Step 3: Create API Application

1. Inside "SWE DRIP" project → New → Application
2. Name: `swe-drip-api`
3. Source: GitHub Repository `kcbdev/SWE-DRIP`
4. Branch: `main`
5. Dockerfile: `Dockerfile.api` (repository root)
6. Domain: `swedrip-api.kcb.ma`
7. Port: `8000`
8. Build Pack: `Dockerfile`

**Environment Variables** (set in Coolify UI):
```
DATABASE_URL=postgresql://swe_drip:<password>@<db-host>:5432/swe_drip
BETTER_AUTH_SECRET=<generate: openssl rand -base64 32>
BETTER_AUTH_URL=https://swedrip-panel.kcb.ma
OPENROUTER_API_KEY=<your-openrouter-key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
FOURTHWALL_API_BASE_URL=https://api.fourthwall.com
FOURTHWALL_API_USERNAME=<shop Open API user, e.g. fw_api_...@fourthwall.com>
FOURTHWALL_API_PASSWORD=<shop Open API password>
FOURTHWALL_WEBHOOK_SECRET=<generate-random>
APP_ENV=production
```

### Step 4: Create Panel Application

1. Inside "SWE DRIP" project → New → Application
2. Name: `swe-drip-panel`
3. Source: GitHub Repository `kcbdev/SWE-DRIP`
4. Branch: `main`
5. Dockerfile: `Dockerfile.panel` (repository root)
6. Domain: `swedrip-panel.kcb.ma`
7. Port: `3000`
8. Build Pack: `Dockerfile`

**Build Arguments** (set in Coolify UI under "Build"):
```
NEXT_PUBLIC_API_BASE_URL=https://swedrip-api.kcb.ma
```

**Environment Variables** (set in Coolify UI):
```
DATABASE_URL=postgresql://swe_drip:<password>@<db-uuid>:5432/swe_drip
BETTER_AUTH_SECRET=<same as API>
BETTER_AUTH_URL=https://swedrip-panel.kcb.ma
NODE_ENV=production
NEXT_PUBLIC_APP_URL=https://swedrip-panel.kcb.ma
COOKIE_DOMAIN=.kcb.ma
```
(`NEXT_PUBLIC_APP_URL` and `COOKIE_DOMAIN` are required — see `Dockerfile.panel`
ARGs. Without `NEXT_PUBLIC_APP_URL` the auth client falls back to
`http://localhost:3000`; without `COOKIE_DOMAIN` the session cookie is host-only
and the API subdomain never receives it.)

### Optional: configure Fourthwall / OpenRouter from the UI

`FOURTHWALL_API_*` and `OPENROUTER_*` can instead (or additionally) be set at
**Settings → Integrations** as an admin. Stored values are server-side, override
the env vars, are never returned by the API (presence only), and "Test
Fourthwall" verifies the connection. Fourthwall credentials are a shop **Open
API user** (Settings → For developers in your Fourthwall dashboard), used as
HTTP Basic against `https://api.fourthwall.com/open-api/v1.0` — not an MCP
token (see `docs/adrs/ADR-005.md`).

### Step 5: Deploy

1. Deploy `swe-drip-db` first (wait for healthy)
2. Deploy `swe-drip-api` (runs migrations on startup)
3. Deploy `swe-drip-panel`

### Step 6: Verify

1. `https://swedrip-api.kcb.ma/api/health` → `{"status": "ok"}`
2. `https://swedrip-panel.kcb.ma` → login page
3. Login with admin credentials (create first user via API or DB)

## Architecture

```
Browser → swedrip-panel.kcb.ma (Next.js :3000)
              ↓ credentials: include
         swedrip-api.kcb.ma (FastAPI :8000)
              ↓
         swe-drip-db (Postgres :5432)
```
