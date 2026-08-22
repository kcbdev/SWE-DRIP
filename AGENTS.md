Plane workspace: kcb
Plane project: 2af62f36-c11a-411a-89b5-8e5a5176b829 # SWDR — SWE Drip (MCP server: plane-kcb)

# AGENTS.md — SWE Drip Constitution

> This repo is bound to Plane `kcb / SWDR (2af62f36-c11a-411a-89b5-8e5a5176b829)` — verified via MCP `plane-kcb`. All `asdlc-plane` sync is scoped to that project. `Backlog` is ignored until moved to `Todo`.

## 1. Stack

| Layer | Choice | Notes |
|---|---|---|
| Docs / Specs | Markdown + YAML | `docs/` is current truth; `specs/` will hold reversed specs per ASDLC |
| Verification | Node 22 + node:test | No external runner required; `npm test` is deterministic gate |
| Infra (target) | Hetzner CX31 + Coolify + Paperclip | Described in `docs/02-stack.md`; not yet provisioned |
| Storefront | Fourthwall (Brutal theme) + Fourthwall MCP | Products/orders/analytics via MCP at `https://mcp.fourthwall.com` |
| LLM/Image/Video | OpenRouter (`https://openrouter.ai/api/v1`) | Claude Sonnet 4.6, Gemini Flash, FLUX.2 Pro, Veo 3.1 Lite |
| Email | Loops.so | Weekly newsletter — `docs/03-agents.md` Email Agent |
| Social | Buffer API | Scheduling for Twitter/X |
| Notifications | Telegram Bot | Founder escalations |

No compiled language yet. Future code PBIs may introduce `agents/`, `workspace/`, `program.md` as described in `docs/` — see ARCHITECTURE.md as-built.

## 2. Commands (deterministic gates)

Run from repo root. All gates must pass before any PBI moves to In Review.

```bash
# Build — docs-only repo, no compilation
cmd /c "npm run build"
# or
npm run build

# Lint — markdown contract checks
cmd /c "npm run lint"
# or
npm run lint   # -> node scripts/lint.js

# Test — smoke suite (node:test, zero deps)
cmd /c "npm test"
# or
npm test       # -> node --test tests/*.test.js

# Full verification (Ralph Loop gate)
cmd /c "npm run verify"
# or
npm run verify # -> build && lint && test
```

Expected results (baseline 2026-08-22):
- `build`: `build: docs-only repo, no compilation required` (exit 0)
- `lint`: `lint: all docs OK` (exit 0)
- `test`: 8 tests, 8 pass, 0 fail via `tests/smoke.test.js`

No PBI may start without a runnable gate. If tests are red, fix gates first.

Windows note (this environment): PowerShell 5.1, `.ps1` wrappers blocked. Use `cmd /c "npm.cmd ..."` / `npx.cmd` or `node` directly. Do not assume POSIX.

## 3. Conventions

- **No change without a spec**: every PBI (including one-line fixes) requires a human-reviewed spec in `specs/{feature}/spec.md` or a compact behavior contract (2–4 sections) for bug fixes. See §B of onboarding skill.
- **Micro-commits**: one logical change per commit, conventional messages (`feat:`, `fix:`, `docs:`, `chore:`), never rewrite legacy history.
- **Spec Reversing gate**: brownfield code is never trusted blindly. Reverse behavior spec, get human review, then implement. Bugs documented as features are defects.
- **Brand invariants**: `#0D0D0D` / `#00FF41` / `#FF6B35`, JetBrains Mono Bold, pricing ($32 tee / $62 hoodie / $20 mug) — do not change without founder approval. Smoke test enforces these.
- **Agent budget discipline**: total OpenRouter cap ~$130/mo; break-even 4–5 shirt sales. Any PBI affecting agent prompts/models must note cost impact.
- **Context Map honesty**: update §5 when structure changes. Stale maps are worse than none.

## 4. Workflow (ASDLC loop)

1. `asdlc-plan` → produces `specs/{feature}/spec.md` + `tasks/PBI-*.md` + `plans/README.md` sequencing
2. `asdlc-execute` → Ralph Loop: implement → gates (`build`/`lint`/`test`) → adversarial + constitutional review → `In Review` vs `Done` sorting
3. `agentic` (deterministic + no human judgment) may close to `Done` directly; `manual` (UX/product/security/production/live verification) stays `In Review` for human gate
4. Every transition out of `Active` carries `PBI-XXX`, `Branch`, `Commits`, `Review` type, and gate summary

## 5. Context Map (Context Mapping practice)

Annotated YAML. Responsibilities per area, not file lists.

```yaml
project_structure:
  docs/:
    responsibility: "Source of truth for brand, stack, agent roster, deployment, launch, traffic, and scale playbooks. As-built contracts; future specs in specs/ override these when implemented."
    contains: "01-brand.md (identity, voice, pricing invariants), 02-stack.md (infra + OpenRouter + Fourthwall MCP), 03-agents.md (11-agent roster + SOUL.md templates), 04-deploy.md (7-day Coolify sequence), 05-launch.md (launch week), 06-traffic.md (organic flywheel + calendar), 07-scale.md (revenue milestones + drift fix)"
  specs/:
    responsibility: "Living specs — human-reviewed behavior contracts per feature (state). The only truth after onboarding. One subdir per feature: spec.md + traces."
    contains: "Not yet created — populated by asdlc-plan via Spec Reversing"
  tasks/:
    responsibility: "PBIs (deltas) — atomic, dependency-declared task cards derived from specs."
    contains: "PBI-{NNN}.md — populated by asdlc-plan"
  plans/:
    responsibility: "Sequencing and progress — index of PBIs, dependency graph, and execution log. Plane sync records Todo seed here."
    contains: "README.md (sequencing + Plane sync section), PROGRESS.md (append-only log)"
  docs/adrs/:
    responsibility: "Architecture Decision Records — structural decisions that change ARCHITECTURE.md."
    contains: "ADR-{NNN}.md per decision"
  tests/:
    responsibility: "Deterministic verification — smoke and contract tests exercising main paths."
    contains: "smoke.test.js (docs contract invariants) — extend per PBI"
  scripts/:
    responsibility: "Local tooling — lint and helpers that gates invoke."
    contains: "lint.js (markdown contract lint)"
  agents/:
    responsibility: "Agent runtime code — CEO live (SKILL.md identity + rules.js pure decision functions, PBI-006); Hermes workers (Trend/Copy/Design/Listing/Social/Video/Analytics/Email/Community/Finance) land via PBI-007..016 on top of agents/lib provider layer (PBI-019)."
    contains: "ceo/SKILL.md + ceo/rules.js (live); lib/config.js + lib/provider.js (PBI-019); souls/*.md per docs/03-agents.md"
  workspace/:
    responsibility: "Shared agent I/O volume (design_briefs.json, listing_copy.json, reports) — schemas + seed live since PBI-005. Simulated locally; in prod mounted as Coolify volume /workspace."
    contains: "design_briefs.json, listing_copy.json (schema-validated), designs/, reports/, fixtures/"

documentation_index:
  README.md:
    answers: "What is SWE Drip, its architecture diagram, stack table, directory map, and quick start (Hetzner+Coolify)?"
  docs/01-brand.md:
    answers: "Who is the customer, what is the voice, what are aesthetic constants (colors/fonts), what are proven slogans, what is the pricing table, and what SEO keywords drive listings?"
  docs/02-stack.md:
    answers: "How is infra provisioned (Hetzner CX31 + Coolify + Paperclip volumes/env vars), how do OpenRouter LLM/image/video calls work (with code samples), and what are Fourthwall MCP tools per agent?"
  docs/03-agents.md:
    answers: "What are the 11 agents, their models/triggers/budgets/outputs, SOUL.md templates, and hiring/firing protocol?"
  docs/04-deploy.md:
    answers: "What is the 7-day deployment sequence, how are VPS/Coolify/Paperclip/workspace seeded, and how are failures troubleshot?"
  docs/05-launch.md:
    answers: "What is the pre-launch checklist, day-by-day launch week playbook (soft launch → PH → HN → Reddit → momentum), and per-channel tactics?"
  docs/06-traffic.md:
    answers: "What are organic traffic engines, what is the automated content calendar, what are 4:1 content ratio rules, and what is the organic flywheel with program.md memory?"
  docs/07-scale.md:
    answers: "What unlocks at each revenue milestone, what is scale arithmetic at $10k MRR, when are paid ads/influencer/collab unlocked, and how is agent drift solved via monthly program.md maintenance?"
  ARCHITECTURE.md:
  program.md:
    answers: "What are the institutional learnings (winning patterns, kill rules, agent performance log) the CEO reads before every decision cycle? Compacted monthly to program-summary.md."
    answers: "What is the as-built snapshot of modules, boundaries, data flows, and known constraints (marked 'not gospel', changeable via ADR)?"
  AGENTS.md:
    answers: "What is the stack, what are gate commands, what are conventions, and where does knowledge live (this Context Map)?"
  specs/{feature}/spec.md:
    answers: "What is the human-reviewed behavior contract for that feature (reversed from code where brownfield)?"
  tasks/PBI-{NNN}.md:
    answers: "What is the atomic delta to implement, its dependencies, and acceptance criteria?"
  plans/README.md:
    answers: "What is the PBI sequencing, dependency graph, and Plane Todo seed (bound to kcb/SWDR)?"
  plans/PROGRESS.md:
    answers: "What has been executed, when, with what gate results and review types?"
```

## 6. Decisions

ADRs live in `docs/adrs/ADR-{NNN}.md`. First ADR will be the onboarding bootstrap itself.

## 7. Verification

See §2. Baseline smoke: `tests/smoke.test.js` (8 tests). Lint: `scripts/lint.js`.

## 8. Plane binding

- Workspace: `kcb` (MCP: `plane-kcb`, header `X-Workspace-slug: kcb`)
- Project: `SWE Drip` — `2af62f36-c11a-411a-89b5-8e5a5176b829` (identifier `SWDR`)
- Verification: `plane-kcb_project.list` returns project `SWDR` — **verified 2026-08-22 via MCP**
- Sync scope: strictly `kcb/SWDR`; `Backlog` ignored until moved to `Todo`; issues route through `asdlc-plan` for Spec/PBI authoring
