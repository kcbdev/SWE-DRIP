# SWE Drip — Deploy Guide

## Quick deploy on Coolify (one-click compose)

1. Coolify → project **swe-drip** → **+ New Resource** → **Docker Compose**
2. Point at this repo: `kcbdev/SWE-DRIP` branch `master`, compose file `deploy/docker-compose.yml`
3. Set env vars:
   - `OPENROUTER_API_KEY` = your sk-or-v1-… key
   - `HERMES_GATEWAY_KEY` = any 64-char hex string
   - `FOURTHWALL_AUTH` = Basic auth header for Fourthwall API
   - `POSTGRES_PASSWORD` = strong password
4. Deploy

## What this replaces

This single compose file replaces:
- The separate Paperclip deployment (`ddglphkkmg5apsosgh7q1crj`)
- The separate Hermes Agent deployment (part of same service)
- All Docker networking / permission / volume issues encountered in Phase 7

## Architecture

```
┌─────────────────────────────────────────────┐
│           swe-drip-net (bridge)             │
│                                             │
│  ┌──────────┐  ┌─────────┐  ┌───────────┐  │
│  │Postgres  │  │Hermes   │  │Paperclip  │  │
│  │:5432     │  │:8642    │  │:3001      │  │
│  └──────────┘  └────┬────┘  └─────┬─────┘  │
│                     │  shared vol │         │
│                     │/home/hermes/│         │
│                     │.hermes      │         │
│                     └─────────────┘        │
└─────────────────────────────────────────────┘
```

- Paperclip dispatches tasks to Hermes at `http://hermes:8642` (same network, no proxy needed)
- Hermes reads OpenRouter key from env, routes to correct model per agent
- Skills persist via shared volume
- Postgres stores Paperclip state durably
