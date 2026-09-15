"""Per-node OpenRouter model routing — **defaults** for the agent control plane.

These are the reviewed baseline and the source of each node's model *class*
(cheap-flash for scoring/vision, Claude for copy/spec, an image model for
render). They are no longer the source of truth: an operator override in the
settings store (`node_config`) wins at run start — see `pipeline/node_config.py`
and `specs/agent-control-plane/spec.md`.

Revision note (2026-09-15, founder-approved, cost-optimized): the previously
"verbatim from the data spec §3" IDs were ALL absent from OpenRouter's live
catalog, so the first live run 404'd. Classes are preserved; IDs are current:

| Node | Model | $/M in-out |
|---|---|---|
| trend_research, aesthetic_qc | `google/gemini-3.5-flash-lite` | 0.30 / 2.50 |
| listing_copy, design_spec | `anthropic/claude-sonnet-5` | 2.00 / 10.00 |
| art_render | `google/gemini-3.1-flash-image` | 0.50 / 3.00 |

Cost impact (AGENTS.md budget discipline, $130/mo cap): a full run is ~5 model
calls, so a run stays far inside the cap; these are the cheapest viable models
in their classes.
"""

from __future__ import annotations

# Current working OpenRouter IDs (verified against the live catalog 2026-09-15).
GEMINI_FLASH_LITE = "google/gemini-3.5-flash-lite"
CLAUDE_SONNET = "anthropic/claude-sonnet-5"
GEMINI_FLASH_IMAGE = "google/gemini-3.1-flash-image"
GPT_IMAGE_MINI = "openai/gpt-5-image-mini"
GPT_IMAGE = "openai/gpt-5-image"

# Locked 11-node order (Vision doc §3.2).
NODE_ORDER: list[str] = [
    "trend_research",  # 1 — scoring + clustering (HITL off)
    "contract_approval",  # 2 — collection contract gate (HITL on)
    "listing_copy",  # 3 — slogan/title/description/tags (off)
    "design_spec",  # 4 — brief vs contract resolution (off)
    "art_render",  # 5 — image generation (off)
    "placement",  # 6 — deterministic placement/colorway (off)
    "aesthetic_qc",  # 7 — vision rubric (on until calibrated)
    "technical_qc",  # 8 — RGBA/dimensions/transparency (off)
    "fw_create",  # 9 — Fourthwall product create, DRAFT-only (no HITL flag)
    "publish_gate",  # 10 — final review before PUBLIC (on)
    "shelf",  # 11 — price invariants + assignment (off)
]

# Nodes with a §3 entry get their exact model; deterministic/external nodes
# (placement C8, technical QC, FW create, publish gate, shelf) make no model
# call and map to None.
MODEL_FOR_NODE: dict[str, str | None] = {
    "trend_research": GEMINI_FLASH_LITE,
    "contract_approval": CLAUDE_SONNET,
    "listing_copy": CLAUDE_SONNET,
    "design_spec": CLAUDE_SONNET,
    "art_render": GEMINI_FLASH_IMAGE,
    "placement": None,
    "aesthetic_qc": GEMINI_FLASH_LITE,  # cheap multimodal variant
    "technical_qc": None,
    "fw_create": None,
    "publish_gate": None,
    "shelf": None,
}

# Art-render fallbacks when the primary image model refuses (set at run start
# in node_config; overridable per node like the primary).
IMAGE_FALLBACKS: tuple[str, ...] = (GPT_IMAGE_MINI, GPT_IMAGE)


def model_for(node: str) -> str | None:
    """Return the routed model for ``node``; loud on unknown nodes."""
    try:
        return MODEL_FOR_NODE[node]
    except KeyError:
        raise KeyError(f"unknown pipeline node: {node!r}") from None
