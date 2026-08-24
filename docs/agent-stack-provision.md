# Agent stack — Coolify provisioning runbook (PBI-033)

Verifies `specs/agent-stack/spec.md` contract 4. All provisioning is done in the
Coolify UI (REST create is unreliable; the MCP server has no create tool). Verify
afterwards via Coolify MCP + HTTP checks.

## Steps

1. Coolify (`https://coolify.kcb.ma`) → project **paperclip** (`dmaobray09x3xj6xe1kb2zke`)
   → **+ New Resource** → **Docker Compose**.
2. Source: `kcbdev/SWE-DRIP` branch `master`, compose file `deploy/docker-compose.yml`.
3. Environment variables (set in the UI, keep as secret where the UI allows):
   - `POSTGRES_PASSWORD`
   - `BETTER_AUTH_SECRET` (`openssl rand -hex 32`)
   - `PAPERCLIP_TOOL_ACTION_SIGNING_SECRET` (`openssl rand -hex 32`)
   - `OPENROUTER_API_KEY`
   - `API_SERVER_KEY` (64-hex; this is the Hermes gateway key — Paperclip agents use it)
4. Domains: bind `https://paperclip.kcb.ma` to the `paperclip` service (port 3100).
   Hermes (8642) stays internal-only — never publish it publicly.
5. Deploy. Watch the deployment log: postgres must become healthy before paperclip starts.

## Verify (contract 4)

- `curl -fsS https://paperclip.kcb.ma/api/health` → 200.
- Coolify MCP:
  - `search_resources { query: "paperclip" }` → new service `running:healthy`
  - `search_resources { query: "hermes" }` → hermes container running
- On the server (or via `docker exec` from Coolify):
  - `docker compose -f ... ps` → postgres healthy, paperclip up, hermes up
  - `docker exec <hermes-container> hermes --version` → ≥ 0.20.5
  - `curl http://localhost:8642/api/health` from inside the stack network → 200

## Rollback / cleanup

- Old resources are **stopped, not deleted**: paperclip app `ddglphkkmg5apsosgh7q1crj`,
  hermes service `kh85cuzhgfz1ib19x6d6es6i`. Do not delete until the new stack has
  passed a full CEO cycle (PBI-034/035).
- Redeploy: Coolify → service → Redeploy (volumes/env preserved).
