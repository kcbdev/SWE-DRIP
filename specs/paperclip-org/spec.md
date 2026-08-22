# Spec: Paperclip Org — SWE Drip autonomous company inside deployed Paperclip

## Goal
Stand up SWE Drip as a **new organization created from scratch** inside the deployed Paperclip instance (`https://paperclip.kcb.ma`), hiring the CEO + 10 Hermes workers with SOUL.md identities materialized from this repo — models, budgets, cron triggers per `docs/03-agents.md`. OpenRouter is already wired (`OPENAI_API_KEY` + `OPENAI_BASE_URL` env, founder-set). This makes Paperclip — not custom code — the execution substrate for the company.

## Scope
- In scope:
  - Create organization `SWE Drip` in Paperclip (founder CEO admin already exists)
  - Materialize 11 SOUL.md files to `agents/souls/` (ceo, trend-scout, copy, design, listing, social, video, analytics, email, community, finance) — content per `docs/03-agents.md` templates: identity, model, trigger, budget cap, tools, output contract, decision rules
  - Hire all 11 agents in Paperclip UI: paste SOUL.md, set model (= registry values from `agents/lib/config.js`), budget cap, cron/on_task trigger
  - Attach Fourthwall MCP server to Paperclip (see `specs/fourthwall-store/spec.md`) so Design/Listing/Analytics/Finance/Social/CEO can call `ecommerce_*` tools
  - End-to-end verification: a first product flows brief→copy→design→live listing through hired agents
- Out of scope:
  - Repo-native worker execution (PBIs 007–018 runtime approach superseded by this spec; their contracts live on as SOUL.md content + Paperclip configuration)
  - OpenRouter key management (done — founder-set)
  - Storefront theme/design (owned by fourthwall-store spec)

## Contracts (success criteria)
1. **Organization exists** — Paperclip shows org `SWE Drip`; founder is admin.
2. **All 11 agents hired and running** — each with SOUL.md content matching `agents/souls/*.md`, model == registry value, budget cap == registry value ($30/$6/$15/$30/$5/$4/$20/$3/$5/$4/$2), triggers per roster (cron Mon 08:00 Trend Scout, Tue-Thu 11am Social, etc., on_task for pipeline).
3. **CEO decision cycle runs** — assign a test task; CEO reads program-summary/program.md, responds on task board without human input.
4. **Pipeline smoke** — one approved brief flows Trend Scout → Copy → Design → Listing producing a draft product via FW MCP tools (full live publish gated by fourthwall-store PBI).
5. **SOUL.md files are lint-gated in repo** — every file present, contains its registry model string + budget cap + trigger (lint check added to `scripts/lint.js`).

## Anti-patterns
- Do not invent new agent roles beyond the 11 in docs/03-agents.md.
- Do not paste SOUL.md content that contradicts `agents/lib/config.js` registry — repo file is source of truth.
- Do not set budgets above registry caps (AGENTS.md §3 budget discipline).
- Do not run pipeline tasks before Fourthwall MCP is connected (PBI-023) — Design Agent would fail its critical path.

## Decisions
- **Decision-1 — Paperclip-native execution supersedes repo-native workers:** PBIs 007–018 contracts are preserved as SOUL.md content + Paperclip config rather than Node worker processes. Recorded in ADR-003. Repo keeps: specs, SOUL sources, program.md memory sync, provider/config libraries (used by future tooling), verification gates.
- **Decision-2 — SOUL files in repo are source of truth:** Paperclip is runtime, not truth. Any agent identity change = edit `agents/souls/*.md` here, re-paste/update in Paperclip.
- **Decision-3 — Hiring order follows dependency:** CEO first, then pipeline (needs FW MCP), then distribution/ops.

## Tooling
- Paperclip UI (human/agent-in-browser) for org creation + hiring — no public API assumed.
- `scripts/lint.js` extension for souls presence/consistency gate.
