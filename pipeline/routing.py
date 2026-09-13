"""Per-node OpenRouter model routing — the SINGLE source of model IDs (spec C3).

Mirrors data spec §3 exactly. Nodes call their designated model directly via
:func:`model_for`; no gateway/override layer exists or may be added (the POC's
known single-model-override bug).

Cost impact (AGENTS.md budget discipline, $130/mo cap): this PBI changes no
model IDs — they are transcribed verbatim from the spec. Aesthetic QC pins the
cheap multimodal variant named in the spec (``google/gemini-2.0-flash-001``);
switching it to a Claude multimodal variant is a config edit here, reviewed
against budget impact per the spec's Decisions.
"""

from __future__ import annotations

# Exact IDs from data spec §3 (verbatim transcription, not invention).
GEMINI_FLASH = "google/gemini-2.0-flash-001"
CLAUDE_SONNET = "anthropic/claude-sonnet-4-6"
RIVERFLOW_PRO = "riverflow-v2-pro"
GPT_IMAGE_MINI = "gpt-5-image-mini"
SEEDREAM = "seedream"

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
    "trend_research": GEMINI_FLASH,
    "contract_approval": CLAUDE_SONNET,
    "listing_copy": CLAUDE_SONNET,
    "design_spec": CLAUDE_SONNET,
    "art_render": RIVERFLOW_PRO,
    "placement": None,
    "aesthetic_qc": GEMINI_FLASH,  # §3: "Claude or Gemini multimodal variant"
    "technical_qc": None,
    "fw_create": None,
    "publish_gate": None,
    "shelf": None,
}

# Art-render fallbacks from §3 (primary riverflow-v2-pro).
IMAGE_FALLBACKS: tuple[str, ...] = (GPT_IMAGE_MINI, SEEDREAM)


def model_for(node: str) -> str | None:
    """Return the routed model for ``node``; loud on unknown nodes."""
    try:
        return MODEL_FOR_NODE[node]
    except KeyError:
        raise KeyError(f"unknown pipeline node: {node!r}") from None
