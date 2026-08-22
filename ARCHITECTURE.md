# ARCHITECTURE.md — SWE Drip (as-built, not gospel)

> **Status: as-built snapshot 2026-08-22.** This document describes the system as it exists today. It is not a prescription; change it via ADR (`docs/adrs/ADR-NNN.md`). Dead structure found later is corrected **here**, not silently in code.

---

## 1. System overview

SWE Drip is a **docs-first, planning-stage** autonomous print-on-demand brand. There is no runtime code in this repo yet. The only truth is the 7 markdown playbooks in `docs/` describing the target agentic system. The repo will materialize code under `agents/`, `workspace/`, and `program.md` as PBIs are planned via `asdlc-plan` and executed via `asdlc-execute`.

Target runtime (described, not yet provisioned):
- **Hetzner CX31** VPS (€8/mo, 4 vCPU / 8 GB / 80 GB NVMe) running **Coolify** (self-hosted PaaS, port 8000, Traefik + Let's Encrypt)
- **Paperclip** (`paperclipai/paperclip:latest`, port 3000) — CEO agent + task board, persists `/app/data` and `/workspace` as Coolify named volumes
- **OpenRouter** `https://openrouter.ai/api/v1` — single OpenAI-compatible key routing to `claude-sonnet-4-6` (CEO/Copy/Email), `gemini-2.0-flash-001` (Trend/Listing/Finance), `claude-haiku-4-5` (Social/Analytics/Community), `flux.2-pro` (image), `veo-3.1-lite` (video)
- **Fourthwall** Brutal theme — storefront, POD fulfillment, payments (MOR), and MCP at `https://mcp.fourthwall.com` (OAuth `FOURTHWALL_MCP_TOKEN`)
- Supporting: Loops.so (email), Buffer (social scheduling), Telegram bot (founder escalations)

## 2. Current as-built modules

| Module | Path | Language / Form | Responsibility | Status |
|---|---|---|---|---|
| **Brand contract** | `docs/01-brand.md` | Markdown | Voice (insider/dry), aesthetic constants (`#0D0D0D`/`#00FF41`/`#FF6B35`, JetBrains Mono Bold), 3 design modes, 7 proven theme clusters, proven slogans, pricing table ($32/$62/$20), SEO keyword tiers | **Live** — enforced by smoke test |
| **Stack contract** | `docs/02-stack.md` | Markdown + Python snippets | Infra diagram (Hetzner→Coolify→Paperclip), Coolify install/volumes/env/healthcheck, OpenRouter LLM/image/video call samples, Fourthwall Brutal CSS + MCP tool table, Loops/Buffer/Telegram configs, monthly cost model (~$75–130, break-even 4–5 shirts) | **Live** |
| **Agent contracts** | `docs/03-agents.md` | Markdown + YAML + JSON schemas | 11 agents (CEO + 10 workers), per-agent model/trigger/budget/output, SOUL.md templates, input/output file contracts (`design_briefs.json`, `listing_copy.json`), decision rules, hiring/firing protocol | **Designed** — runtime not materialized |
| **Deploy sequence** | `docs/04-deploy.md` | Markdown + Bash | 7-day Coolify deployment (Day 1 infra → Day 3 critical design pipeline → Day 7 10 products live), workspace seeding, Coolify operations reference (redeploy, env vars, logs, backups), troubleshooting table | **Playbook** — not yet executed |
| **Launch playbook** | `docs/05-launch.md` | Markdown | Pre-launch checklist, day-by-day launch week (soft → PH → HN → Reddit → momentum), per-channel tactics (Twitter/Reddit/Fourthwall SEO/Email), "what not to do" | **Playbook** |
| **Traffic engine** | `docs/06-traffic.md` | Markdown | 7 organic channels, cron calendar (Mon 8am Trend Scout → Sat 9am Email), 4:1 content ratio enforcement, flywheel diagram (`program.md` as memory), newsletter collab targets, Shorts/TikTok strategy | **Playbook** |
| **Scale playbook** | `docs/07-scale.md` | Markdown | Revenue-milestone unlock sequence ($500 → $20k), $10k MRR arithmetic (526 orders × $38 AOV × 2.5% conv → 21k visitors), paid amplification gate ($5k MRR), influencer/Discord/expansion sequence, drift fix (monthly `program.md` compaction) | **Playbook** |
| **Verification harness** | `tests/smoke.test.js`, `scripts/lint.js`, `package.json` | Node 22 + node:test | 8-test smoke suite asserting docs invariants (existence, pricing, brand constants, agent roster, deployment days); lint checks markdown contracts; `npm run verify` is Ralph Loop gate | **Live** — 8/8 passing |
| **Constitution** | `AGENTS.md` | Markdown + YAML Context Map | Stack/commands/conventions, Context Map (`project_structure` + `documentation_index`), workflow, Plane binding (`kcb/SWDR`) | **Live** |
| **Future: agents/** | `agents/ceo/SKILL.md`, `agents/souls/*.md` | Planned Markdown | CEO skill + per-agent SOUL.md runtime identities. Described in docs/03-agents.md, not yet created. | **Planned** |
| **Future: workspace/** | `workspace/design_briefs.json`, `listing_copy.json`, `/designs/`, `/reports/` | Planned JSON/Markdown/PNG | Shared Paperclip I/O volume. In prod: Coolify volume `/workspace`. Local sim: repo `workspace/` seeded on Day 1. | **Planned** |
| **Future: program.md** | `program.md` | Planned Markdown memory | Institutional knowledge base auto-updated by Analytics Agent; monthly compaction to `program-summary.md` after 90 days. CEO reads before every decision. | **Planned** |

**Single-module truth:** until `specs/` exists, `docs/` is the sole behavior contract. Future PBIs reverse specs from code if brownfield behavior is discovered; specs then override docs.

## 3. Boundaries & dependencies

```
docs/ (source of truth) ──► specs/{feature}/spec.md (human-reviewed, overrides docs when present)
       │
       └─► tasks/PBI-*.md ──► plans/README.md (sequencing) ──► asdlc-execute ──► agents/ + workspace/
                          │
                          └─► tests/*.test.js (gates prove contract)

Runtime target boundaries (future):
  Paperclip CEO orchestrates 10 workers via task board + shared volume
    ├─ read/write /workspace/*.json (file contract, not DB)
    ├─ outbound HTTPS only: OpenRouter, Fourthwall MCP, Buffer, Loops, Telegram, Reddit/Twitter/HN
    └─ no inbound ports except :3000 (Paperclip) and :8000 (Coolify UI) + :443 after SSL
  Fourthwall is Merchant of Record (payments, tax, POD) — no direct Stripe integration
  Coolify volumes (/app/data, /workspace) survive redeploys; only configured storage persists
```

**Explicit non-goals / out-of-scope:**
- No checkout/payment code in this repo (Fourthwall owns it)
- No inbound webhook server yet
- No compiled service — Node `node:test` harness is the only executable code today

## 4. Data flows (target pipeline, 7-agent weekly cycle)

```
Monday 08:00  Trend Scout (gemini-flash) scrapes Reddit/HN/X → scores 0–100 (engagement/novelty/specificity) → /workspace/design_briefs.json (score ≥60)
Monday 10:00  CEO (sonnet) approves brief → assigns Copy Agent
Copy Agent (sonnet) validates uniqueness (FW/TeePublic dupe check) → primary_slogan ≤6 words + fw_title/tags/description + design_prompt_notes → /workspace/listing_copy.json
Design Agent (FLUX.2 Pro → fallback gemini flash image) renders 2048×2048 PNG (JetBrains Mono Bold, #00FF41 on #0D0D0D, flat) → /workspace/designs/[id].png → FW MCP generate-product-design-previews → create-offers-from-designs (product live) → writes URL back to listing_copy.json
Listing Agent (gemini-flash) verifies price ($32/$62/$20), tags, collection, description → confirms live at swedrip.fourthwall.com/products/[slug]
Tuesday 11:00 Social Agent (haiku) posts drop via Buffer (Tuesday drop / Wednesday meme / Thursday engagement, 4:1 ratio)
Monday+Thursday Video Agent (haiku scripting + veo-3.1-lite 8s async, poll 10s × 60) generates clip
Friday 18:00  Analytics Agent (haiku) reads FW analytics → weekly_report.md + kill_list.md (>30d, 0 sales → archive) + scale list (≥5 in 14d) + program.md update
Saturday 09:00 Email Agent (sonnet) sends "The Agent Report" via Loops.so
1st/month     Finance Agent (gemini-flash) reconciles FW payouts vs OpenRouter spend → finance_report.md
Every 12h     Community Agent (haiku) monitors mentions/keywords → replies (no link unless asked)
Continuously  CEO enforces kill/scale/flash-sale rules, budget cap $130/mo, Telegram escalations
```

## 5. Known constraints & risks

| Constraint | Impact | Mitigation / ADR trigger |
|---|---|---|
| **Docs-only repo** — no runtime code to execute | Spec Reversing required before any code change; verification harness only proves docs invariants today | Bootstrap execution via `asdlc-plan` → `specs/` before materializing `agents/`; first code PBI adds real runner |
| **Paperclip not provisioned** — Hetzner/Coolify described but not running | No live agent execution, no `/workspace` volume | Follow `docs/04-deploy.md` Day 1–7 sequentially; don't skip Day 3 (critical path) |
| **FLUX.2 Pro typography fragility** — models stylize text instead of flat mono | Blurry/stylised output fails print-safe gate | Template uses explicit flat-print constraints; fallback to `gemini-3.1-flash-image` with white-mono-on-black fallback prompt |
| **Veo 3.1 Lite async timeout (10 min)** | Video generation may hang, block pipeline | Poll loop with 60×10s + timeout; notify CEO on failure, skip to next product |
| **Budget cap $130/mo** — break-even 4–5 shirts | Agent prompt expansion can breach cap mid-month | Per-agent caps in `docs/03-agents.md` (e.g., Design $30, CEO $30); Finance Agent escalates at 80% by 20th |
| **Agent drift (`program.md` bloat >500 lines)** | CEO context degrades, recycled killed designs reappear | Monthly compaction ADR: Analytics Agent trims to `program-summary.md` (winning patterns + kill rules + last 3mo log) |
| **Fourthwall Morocco/PayPal payout dependency** | Payout failure blocks operations | Verify Dashboard → Payouts → PayPal before launch (checklist in 05-launch) |
| **Windows PowerShell 5.1 env** — `.ps1` wrappers blocked | `npm`/`npx` via `cmd /c` required | Gates documented with `cmd /c` variant; no POSIX assumptions |
| **No compiled language decision yet** | Future PBIs must choose `agents/` runtime (likely Node/Python, but unspecified) | ADR per new language; update AGENTS.md §5 Context Map when `agents/` materializes |
| **Backlog ignored until Todo** | Plane Backlog issues not auto-seeded | Intentional — `asdlc-plane` only syncs `Todo`; move issues to `Todo` to seed PBIs |

## 6. Decision log

ADRs live in `docs/adrs/ADR-NNN.md`. This bootstrap will create `ADR-001` (onboarding: docs-only → ASDLC). Future structural changes (introducing `agents/` language, changing infra from Hetzner, altering pricing) require ADR + AGENTS.md update.

## 7. Verification

Baseline 2026-08-22:
- `npm run build` → `build: docs-only repo, no compilation required` (exit 0)
- `npm run lint` → `lint: all docs OK` (exit 0)
- `npm test` → 8 tests PASS via `tests/smoke.test.js`
- Plane binding verified via `plane-kcb` MCP: workspace `kcb`, project `2af62f36-c11a-411a-89b5-8e5a5176b829 (SWDR)`
- Plane Todo issues: 0 seeded (workspace has 0 `Todo` items in SWDR)
