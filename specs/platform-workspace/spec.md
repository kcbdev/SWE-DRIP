# Spec: Platform — Workspace contracts, program.md memory, CEO orchestration base

## Goal
Establish the shared platform that all 11 agents run against: the `/workspace` file contracts (`design_briefs.json`, `listing_copy.json`, `program.md`, reports), the CEO orchestration loop that reads `program.md` before every decision, and the verification invariants that survive any future code change. Collocated with the `coolify-deploy` infra, this spec makes the factory's I/O deterministic and testable without Paperclip running locally (workspace is a mounted volume in prod, a repo `workspace/` sim in dev).

## Scope
- In scope:
  - Workspace file schemas and lifecycle: `design_briefs.json` (Trend Scout output, scored briefs ≥60, with score_breakdown, source_url, rationale, suggested_aesthetic), `listing_copy.json` (Copy Agent output, primary_slogan ≤6 words, fw_title ≤60, fw_description 150–200w, fw_tags 13, product_types), `weekly_report.md` (KPI table per Analytics Agent), `kill_list.md`/`finance_report.md`, `program.md` + `program-summary.md` (see below), `/designs/*.png` cache, `workspace/reports/`
  - `program.md` as institutional memory: Append-only learnings ("Winning patterns", "Kill rules", "Agent performance"), monthly compaction via Analytics/Email Agent (merge duplicates, archive >90d stale to `## Archive`, trim log to last 3 months, max 500 lines, output `program-summary.md` that CEO reads first after month 3)
  - CEO orchestration base: read `program.md`/`program-summary.md`, enforce decision rules (approve brief ≥60, kill 0 sales 30d → archive via FW MCP, scale 5+ sales 14d → hoodie+mug expand, flash sale if WoW revenue −30% → 20% off top 3), weekly Telegram digest, escalate only on spend>$50 / ban / payout / viral >10k, budget cap $130 total (per-agent caps per `docs/03-agents.md`)
  - Deterministic verification of brand invariants (docs/01-brand): `#0D0D0D`/`#00FF41`/`#FF6B35`/`#FFFFFF`, JetBrains Mono Bold, anti-patterns (no gradients/shadows/pastels/cartoons/motivational/hustle), pricing hard invariants ($32 tee/$62 hoodie/$20 mug/$9 stickers/$25 tote) enforced by smoke/lint (no silent change without founder + ADR)
  - Local simulation of Coolify volume semantics: `WORKSPACE_PATH=/workspace` (env), seed `echo "[]" > /workspace/{design_briefs,listing_copy}.json && mkdir -p /workspace/designs /workspace/reports`, backup `docker run --rm -v paperclip-workspace:/workspace -v /root/backups:/backup alpine tar czf /backup/workspace-$(date +%Y%m%d).tar.gz -C / workspace`
  - AGENTS.md Context Map honesty: update `AGENTS.md:56-130` when `agents/` or `workspace/` materialize; stale maps are defects
- Out of scope:
  - Agent runtime code for Trend/Copy/Design/Listing/Social/Video/Analytics/Email/Community/Finance themselves (their own specs)
  - Real Fourthwall payout or OpenRouter billing reconciliation (mocked with file fixtures here; real calls in `operations` spec)
  - Launch week PR/SEO automation beyond the file contracts (in `storefront`/`operations` specs)

## Contracts (success criteria)
1. **Workspace schemas are JSON-validated and round-trip**
   - `design_briefs.json` validates against `schemas/design_brief.schema.json` (array of {phrase, source_url, score 0–100, score_breakdown {engagement 0–40, novelty 0–30, specificity 0–30}, rationale, suggested_aesthetic enum terminal/minimal/dark-humor, flag nullable}) and refuses `score<60` writes unless `flag` is set for CEO review. `listing_copy.json` validates against `schemas/listing_copy.schema.json` (primary_slogan word-count ≤6, fw_title ≤60, fw_description 150–200w token count, fw_tags length 13). A malformed write fails the `npm test` gate.
2. **program.md lifecycle is deterministic**
   - `program.md` append via `appendProgram(pattern: string)` is idempotent for 60-day deduplication (same phrase from Trend briefs filtered), `program-summary.md` generation keeps all Winning patterns + Kill rules, moves >90d unreinforced patterns to `## Archive`, trims Agent performance log to 90d, and output ≤500 lines — lint check `wc -l program-summary.md` fails if >500.
3. **CEO decision rules are pure functions with tests**
   - `decideApproveBrief(score) → score>=60`, `decideKill(daysSinceLaunch, sales) → days>30 && sales===0`, `decideScale(recent14dSales) → >=5`, `decideFlashSale(wowRevenueChange) → <=-0.30` — unit-tested in `tests/platform.test.js` (node:test) without calling any MCP, 100% branch coverage of the 4 rules + budget guard `sumAgentSpend() <=130`.
4. **Brand invariants are enforcement-tested**
   - Smoke test asserts `docs/01-brand.md` still contains `#0D0D0D`, `#00FF41`, `#FF6B35`, `JetBrains Mono Bold`, `$32`/`$62`/`$20`; a change to those strings requires `docs/adrs/ADR-*.md` + founder note or lint fails (checked in `scripts/lint.js` extension).
5. **Workspace backup/restore is documented and runnable without prod**
   - `scripts/backup-workspace.sh` (POSIX) and `docs/adrs/ADR-*.md` runbook show `docker run --rm -v $(pwd)/workspace:/workspace -v $(pwd)/backups:/backup alpine tar czf /backup/workspace-$(date +%Y%m%d).tar.gz -C / workspace` works locally; `npm run build` does not require Docker but `npm test` includes a skipped-if-no-docker probe.
6. **Context Map stays honest**
   - `AGENTS.md` §5 `project_structure` lists `workspace/` + `agents/` as `Planned` until PBI materializes them; after a PBI lands, the next PBI's review fails if `AGENTS.md` §5 still says `Not yet created` for a landed module (checked via `scripts/lint.js` vs `git ls-files`).

## Anti-patterns
- Do not store workspace JSON as free-form text or HTML — validate against schemas before write.
- Do not let `program.md` grow without compaction — unbounded memory degrades CEO context (drift, see docs/07-scale).
- Do not hardcode pricing or colors in agent prompts — read from `docs/01-brand.md` contract; only `AGENTS.md` + smoke test may canonize them.
- Do not require Paperclip to run `npm test` — file contracts must pass offline (volume is a dir sim).
- Do not mutate `coolify-deploy`'s `Dockerfile`/`nginx.conf`/domain — platform PBIs only touch `workspace/`, `agents/ceo/`, `schemas/`, `scripts/`, and `program.md`.

## Decisions
- **Decision-1 — JSON file contracts over DB for v1:** `design_briefs.json`/`listing_copy.json` as append-logs keep agent I/O inspectable in Coolify volume and git (per docs/04-deploy.md 1.6/1.11). DB migration is an ADR after $5k MRR if needed.
- **Decision-2 — CEO reads `program-summary.md` after 90d:** Full `program.md` past 500 lines is lossy for LLM context — compaction per docs/07-scale (monthly Email Agent task) is code, not a manual doc edit.
- **Decision-3 — Seed script is idempotent `echo "[]"`:** Day-1 `docs/04-deploy.md:1.11` seeding is reproduced locally as `node scripts/seed-workspace.js` that exits 0 if files exist (no overwrite of real data).
- **Decision-4 — Budget is a pure sum, not LLM estimation:** `sumAgentSpend()` reads `workspace/reports/*.json` spend fields — deterministic, no model call in gate.

## Tooling
- Coolify MCP (MCP server, not skill) for volume mount verification on `kcb` (read-only check after `platform-workspace` lands).
- `node:test` + `node --check` only — no new runner; schemas via `ajv` or manual validators (add on approval, prefer zero-deps `node:assert` first).
