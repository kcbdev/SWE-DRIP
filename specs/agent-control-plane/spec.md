# Spec: Agent Control Plane

## Goal

Make every pipeline node's runtime behaviour **operator-configurable from the Control Panel** instead of living in code constants: which model it routes to, its generation parameters, and the prompts/skills it uses — with per-node logs and run inspection good enough to debug a live run from the UI alone.

## Why this reverses two earlier decisions

- `pipeline-core C3` made `pipeline/routing.py` "the SINGLE source of model IDs", transcribed verbatim from the data spec §3.
- The Agents API stated "Model routing is view-only — changes live in `pipeline/routing.py`".

Both were written assuming the spec's IDs were correct. The first live run proved otherwise: **every model ID in the table is absent from OpenRouter's catalog** (`google/gemini-2.0-flash-001`, `anthropic/claude-sonnet-4-6`, `riverflow-v2-pro`, `seedream` → all `NOT FOUND`; `gpt-5-image-mini` needs an `openai/` prefix). A4/A6 were verified against the routing *table*, not against OpenRouter, so the routing surface was silently non-functional. Hardcoded IDs also mean every model change is a deploy.

`pipeline/routing.py` becomes the **defaults**, not the source of truth.

## Scope

- In scope: a per-node runtime config store (model, generation params, prompt overrides, enabled flags); model selection validated against the live OpenRouter catalog; prompt-override versioning so calibration stays honest; per-node run logs; deeper run visualisation/exploration.
- Out of scope: changing the 11-node order or HITL semantics; executing operator-supplied code (see C6); per-run ad-hoc overrides that bypass the store (a run is reproducible from the store + contract).

## Contracts (success criteria)

- **C1 — Per-node config, store-backed**: one settings key (`node_config`) holds `{node: {model, params, prompt_override, enabled, notes}}`. Resolution is layered: **code defaults < store override**. Missing keys fall back to defaults, so an empty store behaves exactly as today.
- **C2 — Read at run start, frozen per run**: a run resolves its config once at start and passes it through `config["configurable"]["node_config"]`. Mid-run edits never change a running run (same rule as HITL flags). The run's resolved config is recorded in state so any run is explainable after the fact.
- **C3 — Model must exist (this is the bug-prevention contract)**: a model may only be set to an ID present in the OpenRouter catalog; free-text model IDs are rejected with the catalog's closest matches. This structurally prevents the dead-ID failure that broke the first live run. The catalog is fetched live and cached; a stale cache serves reads but never authorises a write.
- **C4 — Prompt overrides are versioned**: `aesthetic_qc`'s rubric is calibrated against `RUBRIC_VERSION` pins. An override changes the effective prompt, so the node's verdict must carry a `prompt_version` derived from (base version + override hash). Calibration compares like with like or says so explicitly — an override can never silently look "calibrated".
- **C5 — Cost discipline**: model and param changes require a `cost_impact_note` and are audited (before/after). The Agents screen shows per-node spend against cap (already shipped) so a change is made with its cost visible.
- **C6 — No arbitrary code, ever**: "skills" means declared, enumerable capabilities per node (e.g. enabling an optional tool), never operator-authored code executed by the pipeline. Prompts are data (strings + params), not executable. There is no path from the Control Panel to run operator-supplied code.
- **C7 — Per-node logs**: every node emits structured log rows (`run_id, node, level, message, ts`) persisted server-side, queryable per run and per node, streamed live, and secret-redacted. A failed node's reason is visible in the UI without reading container logs.
- **C8 — Run visualisation**: the Runs screen shows the 11 nodes as a status-coloured flow (complete / current / awaiting-approval / failed / not-reached), each node's duration, per-node logs, and its state slice — plus run-level filtering and search. Answering "which node failed and why" must take one screen.

## Anti-patterns

- Hardcoding a model ID again, or accepting one that the catalog does not know.
- Letting a mid-run config edit affect a run in flight.
- Executing operator-supplied code or evaluating operator-supplied expressions.
- Treating a prompt override as still "calibrated" without a version change.
- Storing the config anywhere other than the single settings store (no parallel config file).
- Logging secrets (tokens, keys, full request bodies containing credentials).

## Decisions

- **`pipeline/routing.py` keeps the defaults.** It stays the reviewed baseline and the source of per-node model *classes*; the store overrides it at runtime. Removing the defaults would make an empty store unusable.
- **Defaults updated to current, working IDs** (founder choice, 2026-09-15, cost-optimized): trend + aesthetic QC → `google/gemini-3.5-flash-lite` ($0.30/$2.50 per M); copy + design spec → `anthropic/claude-sonnet-5` ($2.00/$10.00); art render → `google/gemini-3.1-flash-image` ($0.50/$3.00); fallbacks `openai/gpt-5-image-mini`, `openai/gpt-5-image`. A full run is ~5 model calls, so these defaults keep a run well inside the $130/mo cap.
- **Model catalog endpoint** (`GET /api/agents/models`) is read-only and cached; the UI picker is populated from it, which is also what makes C3 enforceable.
- **`enabled: false` skips the node's model call**, not the node — the node still records its absence explicitly in run state (never a silent skip).
- **Per-node logs are a separate surface from the audit log.** Audit = who changed what; logs = what happened during a run. They must not be merged.
