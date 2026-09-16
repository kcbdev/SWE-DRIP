# Spec: Collection Research

## Goal

Give collections a real creative layer: a slower, monthly-cadence research
pipeline that turns inspiration (curated references) and artistic synthesis
into locked collection contracts with visual direction — mood, graphic
vocabulary, and directives — so item runs inherit taste instead of inventing
it, each collection is internally coherent, and collections stay diverse
from each other across rotation.

## Scope

- In scope: naming the 7 locked brand styles (founder decision, closes the
  PBI-011 gap); contract schema v2 with visual fields (additive, backward
  compatible); inspiration ingest (operator-curated uploads + links + notes);
  a collection-research graph (synthesize → mood-board render → draft →
  CEO gate) feeding the existing collections lifecycle; style-conformance
  QC against the mood board; a lineage/diversity check against
  active/retired collections; rotation-queue surfacing.
- Out of scope: automated web harvesting from Threadless/Etsy (ToS risk —
  curation-in only until an API-or-permission decision exists); executing
  operator-supplied code; changing the 11-node item graph or its HITL
  semantics; per-item style invention (still forbidden — inheritance only);
  log retention beyond the documented caps.

## Contracts (success criteria)

- **C1 — Managed style repository**: the 7 brand styles live in
  `collections/styles.yaml` (names + graphic definitions + version), not in
  code: readable by agents (research synthesis, validation) and manageable
  from the UI (create/edit with audit, founder-gated). `style_archetype`
  validates against the repo instead of any non-empty string. Agents may
  propose directives within the locked vocabulary but never mint styles —
  creation is human (UI) or spec-amendment. Changing the list is a spec
  amendment, not a code tweak.
- **C2 — Visual contract fields**: v2 adds `style_descriptors`
  (graphic-vocabulary strings), `mood_board` (artifact refs),
  `inspiration_refs` (URLs + notes), and `avoid` (anti-references) — all
  optional, so every v1 contract still validates byte-identically. Prompt
  text never travels in these fields beyond the override rules of the
  agent-control-plane spec.
- **C3 — Inspiration ingest**: images (PNG/JPEG) and links attach to a
  draft candidate with notes, served back read-only; non-images and
  oversized uploads are rejected loudly. Assets live beside the contract
  (`collections/<slug>.assets/`, same single-source rule as the YAML).
- **C3b — Durable artifacts**: every artifact the system creates — mood
  boards, inspiration uploads, run renders — lives under env-driven roots
  backed by a persistent volume in Coolify (no more container-ephemeral
  wipes on redeploy). Paths stay same-shape locally (repo-relative
  defaults) so offline gates are unaffected.
- **C4 — Research graph**: a second, monthly-cadence graph —
  `inspiration → style synthesis → mood-board render → contract draft →
  CEO approval gate` — reusing the checkpointer, HITL, cost-logging, and
  run-log patterns. Its drafts enter the existing collections lifecycle
  (candidates → approve → active); it never writes `active` directly.
- **C5 — Coherence within**: the aesthetic-QC rubric gains a
  style-conformance criterion scored against the collection's mood board
  (not the text prompt); a composition-passing but style-betraying render
  fails loudly with the criterion named.
- **C6 — Diversity between**: a lineage record (past archetypes, palettes,
  motifs) feeds synthesis as negative context, and a draft-time check
  flags near-duplicates of active/retired collections instead of
  approving silently. The rotation queue always shows the next queued
  candidate so rotation never stalls waiting on research.

## Anti-patterns

- Inventing a style per item or per run (all style decisions live in the
  locked contract; nodes inherit, never decide).
- Scraping inspiration sources against their ToS, or hotlinking third-party
  images into products or boards (uploads are copies with provenance notes).
- Treating a mood board as decoration: if QC cannot score against it, it
  is not wired up — remove it or wire it.
- Comparing a verdict against a changed prompt/board without a version
  change (the agent-control-plane calibration-honesty rule applies to
  visual versions too: board revisions bump a `board_version` carried in
  verdicts).
- Storing research state anywhere but the collection record (no parallel
  inspiration database).

## Decisions

- **Second graph, not node bloat**: item runs stay daily/mechanical;
  research runs monthly/creative. Separate cadence, cost profile, and gates
  (Vision §3: collections are the unit of creative strategy).
- **Curation-in for v1**: no web-fetch node until a source API or explicit
  permission exists (Threadless/Etsy ToS). The curator step doubles as the
  founder-taste injection point.
- **Mood boards are generated sheets** (image model, style samples — never
  products), stored as run artifacts referenced by the contract, served
  same-origin like renders.
- **Capability discovery (2026-09-16)**: no skills.sh adoption — best
  matches (`rampstackco brand-style-guide` 289 installs,
  `mike-coulbourn visual-identity-direction` 155,
  `gtmagents mood-board-builder` 104) sit below the 1K-preferred bar and
  cover generic branding, not apparel-graphic research; the stack's own
  OpenRouter text/image models + HITL gates already provide the mechanics,
  and taste decisions stay founder-gated by design.
- **Asset durability note**: resolved by C3b — persistent volume from the
  start, not as a follow-up. Until the volume lands in Coolify, assets
  remain container-ephemeral (same as `runs/` renders today).

## Tooling (optional)

- None adopted. Provable with the existing chain (`pytest`, `vitest`,
  `verify`, parity harness extended for the research graph shape).
