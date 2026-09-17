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
SWE_DRIP_RUNS_DIR=/app/runs
SWE_DRIP_COLLECTIONS_DIR=/app/collections
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

## Persistent storage (volumes) — PBI-053
Renders (`runs/`) and collection contracts + assets (`collections/`) are
plain container files. Without mounts every redeploy wipes them. Mount two
persistent volumes on **`swe-drip-api`** (Coolify → Application → Storages):

| Volume handle | Container mount path | Env var (already set above) | Holds |
|---|---|---|---|
| `swe_drip_runs` | `/app/runs` | `SWE_DRIP_RUNS_DIR=/app/runs` | item renders (`render.png`, regens) |
| `swe_drip_collections` | `/app/collections` | `SWE_DRIP_COLLECTIONS_DIR=/app/collections` | contracts (`*.yaml`), `styles.yaml`, asset dirs (`*.assets/`, boards, uploads) |

Notes:

- The code resolves both roots through `pipeline/paths.py`: the env vars
  win when set, otherwise the repo-relative defaults apply. Local dev and
  every offline gate (`npm run verify`) need no env and no volumes.
- Backups: Coolify volume snapshots (Storage → Snapshots). No backup
  automation lives in this repo — snapshots are the documented mechanism.
- Local-dev equivalence: run bare (`python -m pytest …`, `next dev`);
  defaults just work against `./runs` / `./collections`.
- No backfill: artifacts written before the volumes attach are
  container-ephemeral and already gone after the next redeploy. Renders
  can be regenerated (run replay); boards/uploads must be re-curated.
- First attach seeds empty: `Dockerfile.api` ships only `api/` +
  `pipeline/`, so a fresh volume has no `styles.yaml` and no contracts
  (the approval gate fails loudly until they exist). Seed once after
  attaching: copy the repo's `collections/` (contracts + `styles.yaml`)
  into the `swe_drip_collections` volume before the first approval.

## Local UI verification (dev auth bypass — PBI-057)

Skip real credentials while developing the interface:

1. `docker compose up -d db` (audit writes + sessions need Postgres),
   then run migrations + API + panel locally with the bypass on:
   ```
   $env:SWE_DRIP_DEV_AUTH_BYPASS = "dev@local"   # PowerShell
   python -m api.app.migrations
   uvicorn api.app.main:app --port 8000 &
   cd control-panel; npm run dev                  # :3000
   ```
2. Open `http://localhost:3000` — every page renders as admin, every API
   call carries the `dev-bypass` audit identity (never a real user id).
3. Unset the variable (or set `FALSE`) to return to normal auth.

NEVER set `SWE_DRIP_DEV_AUTH_BYPASS` in Coolify (or any production env):
the API refuses to boot with `APP_ENV=production` while it is set, and
the panel ignores the flag there.

## Operator MCP doorway (`/mcp`)

Machine clients (agents, CLIs) authenticate with scoped Bearer tokens —
Better Auth cookies are browsers-only. Full decision record:
`docs/adrs/ADR-006.md`.

### Issuance (admin session required)

1. `POST https://swedrip-api.kcb.ma/api/operator-tokens`
   `{"name": "opencode-runner", "scopes": ["operate"]}` → `201` with
   `{"token": "sdr_…", "prefix": "sdr_…", …}`.
2. **Copy the token now — it is shown once, never again.** Vault it
   (password manager / server secret store), never chat logs or code.
3. Scopes: `read` (observers: runs, logs, approvals, agents, catalog,
   collections, audit, calibration, graph, research runs, styles,
   boards) vs `operate` (read + run start, approval decisions, agent
   config, replay, research start/decisions, style create/update). Issue
   least privilege.

### Rotation / revocation

1. Issue the replacement token first, switch the client, then
   `POST /api/operator-tokens/{id}/revoke` the old one.
2. `GET /api/operator-tokens` lists metadata (prefix, scopes, activity) —
   hashes never leave the store.
3. Every issuance and revocation writes an audit row (`operator_token.*`,
   prefix only).

### Client config (Claude Code / Opencode, remote HTTP)

```json
{
  "mcpServers": {
    "swe-drip-operator": {
      "type": "streamable-http",
      "url": "https://swedrip-api.kcb.ma/mcp/",
      "headers": { "Authorization": "Bearer sdr_…" }
    }
  }
}
```

### Smoke (after deploy)

1. No token: `POST /mcp/` → `401`.
2. Read token: MCP handshake → `runs_list`, `graph_inspect` (11 nodes),
   `research_runs_list`, `styles_list` (25 tools total).
3. Operate token dry probe: `agent_config` with a dead model ID →
   `Unknown model … [422]` with suggestions (no state changed).
4. Revoke the smoke token → next call `401`.

## Architecture

```
Browser → swedrip-panel.kcb.ma (Next.js :3000)
              ↓ credentials: include
         swedrip-api.kcb.ma (FastAPI :8000)
              ↓
         swe-drip-db (Postgres :5432)
```
