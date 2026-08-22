# Spec: LLM Config — Hermes agent runtime + OpenRouter provider layer

## Goal
One shared, testable configuration layer that every Hermes worker (Trend Scout, Copy, Design, Listing, Social, Video, Analytics, Email, Community, Finance) and the CEO use to talk to OpenRouter — model routing per `docs/03-agents.md`, budget caps enforced, API key injected at runtime only (founder sets it in Paperclip UI or Coolify env when ready; never baked into code or image).

## Scope
- In scope:
  - `agents/lib/config.js` — machine-readable agent registry mirroring `docs/03-agents.md` roster: 11 agents × {name, model, trigger, budget_cap_usd_month, output}. Single source of truth for code; docs stay human truth.
  - `agents/lib/provider.js` — OpenRouter client factory (`callLLM`, `generateImage`, `generateVideo` request builders): base URL from `OPENAI_BASE_URL` env (default `https://openrouter.ai/api/v1`), auth from `OPENROUTER_API_KEY` || `OPENAI_API_KEY`. Missing key → explicit error message telling the founder exactly where to set it (Paperclip UI env vars or Coolify → swedrip → Environment Variables) — never a silent failure, never a hardcoded key.
  - Budget guard: `sumAgentSpend()` reads `workspace/reports/*.json` spend fields; `assertBudgetCap()` fails when projected total > $130/mo (AGENTS.md §3 discipline).
  - Model routing table enforced by test against `docs/03-agents.md` values: CEO/Copy/Email = `anthropic/claude-sonnet-4-6`; Trend/Listing/Finance = `google/gemini-2.0-flash-001`; Social/Analytics/Community = `anthropic/claude-haiku-4-5`; Design image = `black-forest-labs/flux.2-pro` (+ fallback `google/gemini-3.1-flash-image`); Video = `google/veo-3.1-lite`.
  - Request-shape contracts matching `docs/02-stack.md` samples: chat `/chat/completions` {model, messages}, images `/images` {model, prompt, image_config:{2048,2048}}, videos `/videos` POST + poll GET `/videos/{id}`.
- Out of scope:
  - Actual network calls in gates (all mocked; live calls happen inside Paperclip runtime once founder sets the key)
  - Storing/rotating the key itself (founder-owned; env names only in repo)
  - Agent business logic (owned by PBI-007…016 which import this layer)

## Contracts (success criteria)
1. **Registry mirrors docs roster** — `getAgent(name)` returns model/trigger/budget for all 11 agents; `test` asserts each value equals the `docs/03-agents.md` table (parse or hardcode-with-comment referencing doc line).
2. **Provider request shapes are exact** — mocked `fetch` captures: chat body `{model, messages:[{role,content}...]}`, headers `{Authorization: Bearer <key>, Content-Type: application/json}`; image body includes `image_config:{width:2048,height:2048}`; video POST `{model:"google/veo-3.1-lite", duration:8}` + poll loop GET every 10s ≤60 tries.
3. **Missing key fails loud with founder instructions** — `provider.callLLM()` without `OPENROUTER_API_KEY`/`OPENAI_API_KEY` throws error containing "set OPENROUTER_API_KEY" and "Paperclip UI" guidance; no network attempt.
4. **Budget cap enforced** — fixture reports summing >130 → `assertBudgetCap()` throws naming the over-budget agents; ≤130 passes.
5. **No secrets in repo** — grep gate: no `sk-or-` pattern anywhere in tracked files; `.coolify/app.json` env catalog lists key names only.

## Anti-patterns
- Do not hardcode any API key or placeholder that looks real.
- Do not let agents construct their own base URLs — always via `provider.js`.
- Do not silently downgrade models to save cost — routing changes require spec + ADR (cost impact note per AGENTS.md §3).

## Decisions
- **Decision-1 — OpenRouter-only provider:** single key covers LLM+image+video per `docs/02-stack.md`; swapping providers is an ADR.
- **Decision-2 — Key injection deferred to founder:** runs fine without key until a live call is attempted; error message is the setup instruction (Paperclip UI preferred since CEO orchestrates there).

## Tooling
- Zero-dep: global `fetch` (Node 22), `node:test` mocks via injectable fetch.
