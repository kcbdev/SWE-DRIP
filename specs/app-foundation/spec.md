# Spec: App Foundation

## Goal

Stand up the polyglot monorepo skeleton for SWE Drip V1 — the Next.js 15 Control Panel, the FastAPI Control Panel API, and the LangGraph pipeline package — with deterministic polyglot gates and a local-development Postgres harness, so every subsequent PBI lands on a verified base.

## Scope

- In scope: repository layout; toolchain scaffolding (Next.js/shadcn, Python/FastAPI/LangGraph); brand-theme shell; env/secrets template; local Postgres via Docker Compose; extension of the root `verify` chain to cover both stacks.
- Out of scope: any product feature (auth, audit, pipeline nodes, screens); deployment/Coolify; CI pipelines; storefront anything.

## Contracts (success criteria)

- **C1 — Layout is fixed**: `control-panel/` (Next.js 15 + shadcn/ui), `api/` (FastAPI), `pipeline/` (LangGraph package importable by the API — single deployable), `collections/` (runtime contract YAML) exist with those responsibilities; recorded in ADR-002 and the AGENTS.md Context Map.
- **C2 — Control Panel shell builds brand-true**: `next build` passes; the app is dark-theme only (void black `#0D0D0D`, terminal green `#00FF41` accent, JetBrains Mono for data/mono content); no gradients, shadows, rounded pills, or pastels; a smoke test asserts the brand tokens.
- **C3 — API serves health**: `GET /api/health` returns `{"status":"ok"}`; the app target `api.app.main:app` imports cleanly; pytest suite green.
- **C4 — One deterministic root gate**: `cmd /c "npm run verify"` runs docs build/lint/test + Control Panel build/test + pytest, fully offline (no network, no DB, no external service required).
- **C5 — Secrets discipline**: `.env.example` lists every required variable with placeholder values only (`BETTER_AUTH_SECRET`, `DATABASE_URL`, `OPENROUTER_API_KEY`, `FOURTHWALL_MCP_TOKEN`, …); the secret scan in `scripts/lint.js` stays green.
- **C6 — Local dev DB**: `docker compose up -d db` provides a pgvector-capable Postgres 17 for integration work; unit-level gates (`npm run verify`) never require it.

## Anti-patterns

- Committing real secrets or `.env` files.
- Introducing a second web framework, a second API framework, or splitting the pipeline into a separate deployable (that is an ADR-gated change).
- Weakening or deleting the existing docs-contract checks in `scripts/lint.js` / `tests/smoke.test.js`.
- Light-theme support, gradient/shadow/pastel styling, or rounded pills anywhere in the Control Panel.
- Making `npm run verify` depend on network access or a running database.

## Decisions

- ADR-002 — repo layout, flat-package Python project, single-deployable pipeline execution.
- Tooling adopted at planning: `fastapi/fastapi@fastapi` skill, `langchain-ai/langchain-skills@langgraph-python-quickstart` skill (official sources).
