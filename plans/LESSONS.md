# Lessons — operator-mcp chain (PBI-043…046, 2026-09-16)

> Draft — human-gated. This file is a proposal until the founder approves it.

## What worked

- **Calling router functions directly from MCP tools** gave REST parity by
  construction; the byte-equality test then proves rather than hopes.
- **Live-loopback conformance** (uvicorn, ephemeral port) over a real SDK
  client: caught the lifespan cascade failure, the `_body` model-shadowing
  bug, and the async-fake mismatch — none of which unit tests would see.
- **Adversarial review before close-out** paid twice: by-id revoke lookup,
  Query-limit clamping, selection passthrough, and the role-mapping
  reconciliation all came from the critic, not the author.
- **Probing SDK behavior empirically** (lifespan cascade, error surfacing,
  stateless mode) before committing to a design — five minutes of probes
  saved a broken production mount.

## What failed / cost time

- **Assuming TestClient suffices for ASGI-lifespan apps**: two wasted
  iterations before switching to the repo's live-uvicorn pattern. Rule:
  if the dependency needs lifespan/task-groups, go straight to loopback.
- **Bulk `sed`-style rewrites via shell**: two corruptions (paren
  imbalance, stray non-ASCII token) from PowerShell string handling. Rule:
  mechanical multi-site edits go through the Edit tool, never shell text
  munging.
- **Parallel Plane creates scramble sequence numbers**: SWDRP-43…46 map to
  PBI-046/044/043/045 respectively. Rule: create Plane issues sequentially
  when identifier order matters, or accept and record the mapping.
- **Over-strict test assertion fighting the design** (`plaintext not in
  str(rows)` vs intentional prefix substring): assert the precise claim
  (no field equals the token), not a sweeping one.

## Do differently next time

- Check installed major versions of SDK deps (`mcp` 1.x vs 2.x) at planning
  time, not mid-implementation — the FastMCP→MCPServer rename shaped the
  whole mount design.
- Write the transport-lifespan probe as the first test, not the last resort:
  "does the mount serve one authenticated call?" gates everything else.
- Keep a standing rule: any synthesized-identity helper gets its
  "what-enforces-what" contract in the docstring on day one (scope vs role),
  before a critic has to ask.
