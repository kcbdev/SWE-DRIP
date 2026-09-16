# Spec: Operator MCP

## Goal

Give an AI operator a second, remotely operable doorway into SWE Drip V1 over
the Model Context Protocol (Streamable HTTP): trigger runs, read runs/logs/
approvals/agents/catalog/audit/calibration, and tune per-node runtime config
(model, params, enabled, prompt overrides) — with **the same enforcement as
the Control Panel UI** (RBAC, validation, cost guards, audit), so test and
calibration loops can run without container access or a browser session.

## Scope

- In scope: token auth for machine clients; MCP mount in the existing
  deployable; read tools mirroring the REST shapes; write tools reusing the
  service layer (run start, approval decide, agent config patch, replay);
  read-only graph inspection (locked order, edges, per-node state keys and
  config source); operator runbook + live smoke.
- Out of scope: structural graph mutation (add/remove/reorder nodes, edit
  edges) — the 11-node locked order is a Vision §3.2 invariant enforced by
  the parity harness and `NODE_ORDER` asserts; changing it needs a spec
  amendment plus code, never an API call. Also out: OAuth/DCR login flows
  (tokens only), per-run ad-hoc overrides bypassing the store, log
  retention/rotation beyond the documented read cap, executing
  operator-supplied code.

## Contracts (success criteria)

- **C1 — Token auth, no cookies**: machine clients authenticate with scoped,
  long-lived operator tokens (Bearer). Tokens are hashed at rest, shown once
  at issuance, revocable; issuance/revocation are Admin-only and audited.
  Cookie/session auth is not accepted on `/mcp`. Invalid or revoked tokens
  get 401/403, never a stack trace. Scopes: `read` (all read tools) and
  `operate` (read + write tools).
- **C2 — Read parity**: every read tool returns the same shape as its REST
  twin (runs list/detail/logs, approvals queue, agents roster, model
  catalog, prompt meta, collections, audit, calibration/designs). One
  implementation serves both doorways — the MCP layer maps, never
  re-implements.
- **C3 — Writes reuse enforcement**: run start, approval decide, agent config
  patch, and replay call the same service functions as the routers, so
  catalog validation (422 + suggestions / 503 unverifiable), cost-impact
  notes (required), the $130 cost guard (409), run-start-explicitness, and
  audit rows behave identically. A tool call that the REST layer would
  reject is rejected the same way. Role checks are subsumed by scope checks:
  `operate` scope is issued only by admins, so it authorizes every write the
  tools offer (including admin-only agent config); audit rows carry the token
  identity, never a human.
- **C4 — Graph visibility without mutation**: an inspection tool reports the
  locked node order, the register_node edges, each node's state key, and
  where its config resolves from (defaults vs store). No tool adds,
  removes, reorders, or rewires nodes.
- **C5 — Secrets discipline**: token values appear exactly once (issuance
  response) and never in logs, errors, or audit rows (hash/prefix only);
  prompt text stays write-only as in the REST layer; run payloads are the
  trimmed shapes, never full state dumps with credentials.
- **C6 — Same deployable, gated**: the MCP server mounts in the FastAPI app
  (`/mcp`, no new hosting, no new database). Offline gates gain an
  MCP-conformance test over loopback-local transport (ephemeral port — the
  SDK's session lifespan cannot run in-process, proven by probe, same reason
  `test_stream.py` uses live uvicorn; no external network, no DB);
  `npm run verify` is extended, never weakened.

## Anti-patterns

- A second enforcement path: any validation, RBAC check, cost guard, or
  audit row the REST layer performs and the MCP layer skips.
- Executing operator-supplied code or evaluating operator-supplied
  expressions (tools are a fixed set with typed inputs).
- Structural graph mutation through any tool (see C4).
- Accepting session cookies on `/mcp`, or logging/replaying token values.
- A parallel state copy (tools read the checkpointer, settings store, and
  collection YAML only).

## Decisions

- **Transport**: FastMCP (the `mcp` package is already a dependency;
  server-side use is new) over Streamable HTTP, mounted in `api/app/main.py`
  at `/mcp`. ADR-006 records the decision (PBI-046).
- **Auth model**: scoped Bearer tokens in a new `operator_tokens` table,
  `sha256(salt + token)` at rest, `sdr_` prefix for identification without
  disclosure. No OAuth/DCR (the Fourthwall lesson in ADR-005 applies:
  interactive flows don't serve machine clients).
- **Scope split**: `read` vs `operate`; write tools require `operate`.
  Approval decisions and run starts are `operate` (production-impacting).
- **Graph mutation stays out**: add/remove/reorder would silently break the
  A4/A5/A6 parity gates and every `NODE_ORDER` assert. Enable/disable plus
  per-node config already covers operational tweaking; structural change
  stays a code + spec-amendment path.
- **Skill candidates** (founder decision 2026-09-16): none — the build
  uses the official `modelcontextprotocol/python-sdk` directly (already a
  declared dependency in `pyproject.toml`; server-side use is new, no new
  install). No skills.sh wrapper needed.

## Tooling (optional)

- Adopted on approval (recorded in `plans/README.md` gate plan): one of the
  two MCP build skills above, used for transport/auth conformance review.
- Test path: the `mcp` SDK's in-memory client for conformance tests
  (no network); existing `pytest` + `verify` chain extended.
