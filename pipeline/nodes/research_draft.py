"""Research node 4 — contract draft (spec C4).

Assembles the v2 collection contract from the synthesized directives and
the reviewed inspiration: locked fields filled, everything unknowable left
as explicit empty placeholders (the node-2 no-invention rule applies
unchanged). Shape-validated before output; an invalid draft is loud, never
a silent candidate. No filesystem writes — drafts travel in state into the
existing collections lifecycle (PBI-020), which owns persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..collection_graph import RESEARCH_DEFAULT_HITL, register_research_node
from ..runlog import get_logger
from .contract import CONTRACT_KEYS, slugify, validate_contract

NODE = "contract_draft"


def assemble_draft(
    slug: str,
    theme: str,
    style_archetype: str,
    synthesis: dict[str, Any],
    inspiration: dict[str, Any],
    board_version: int = 1,
) -> dict[str, Any]:
    """Build the v2 draft from research outputs (pure, deterministic)."""
    refs = [
        {"url": r["url"], "note": r.get("note", "")}
        for r in (inspiration.get("refs") or [])
        if isinstance(r, dict) and r.get("url")
    ]
    return {
        "collection_id": slug,
        "theme": theme,
        "status": "draft",
        "style_archetype": style_archetype,
        "illustration_rules": {"line_weight": None, "palette": [], "no_mixed_styles": True},
        "garment_colorways": [],
        "placement_templates": [],
        "product_count_target": None,
        "lifecycle_days": None,
        "kpi_thresholds": {"min_units": None, "min_conversion": None, "eval_window_days": None},
        "created_by": "research-graph",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_at": None,
        "retired_at": None,
        "survivor_products": [],
        "style_descriptors": list(synthesis.get("style_descriptors") or []),
        "mood_board": [],
        "inspiration_refs": refs,
        "avoid": list(synthesis.get("avoid") or []),
        "board_version": board_version,
    }


def contract_draft(
    state: dict[str, Any], config: RunnableConfig = None  # type: ignore[assignment]
) -> dict[str, Any]:
    """Node 4 implementation: assemble → shape-validate → state."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, RESEARCH_DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})
    log = get_logger(cfg)
    rid = str(cfg.get("thread_id") or "")
    synthesis = state.get("synthesis")
    inspiration = state.get("inspiration")
    if not synthesis or not synthesis.get("style_descriptors"):
        log.error(NODE, "no synthesis with style_descriptors in state", run_id=rid)
        return {
            "visited": [NODE],
            "errors": [f"{NODE}: no synthesis with style_descriptors in state"],
        }
    if not inspiration:
        log.error(NODE, "no reviewed inspiration in state", run_id=rid)
        return {
            "visited": [NODE],
            "errors": [f"{NODE}: no reviewed inspiration in state"],
        }
    slug = slugify(str(state.get("collection_theme") or state.get("collection_slug") or "untitled"))
    # Style comes from the caller (CEO brief or synthesis target), not from
    # the model — a blank here is recorded, never defaulted.
    if not state.get("style_archetype"):
        log.error(NODE, "no style_archetype supplied for the draft", run_id=rid)
        return {
            "visited": [NODE],
            "errors": [f"{NODE}: no style_archetype supplied for the draft"],
        }
    draft = assemble_draft(
        slug=slug,
        theme=str(state.get("collection_theme") or slug),
        style_archetype=str(state.get("style_archetype")),
        synthesis=synthesis,
        inspiration=inspiration,
        board_version=int((state.get("board") or {}).get("board_version") or 1),
    )
    problems = validate_contract(draft)
    if problems:  # self-invalid draft is a code bug — loud, never silent
        log.error(NODE, f"assembled an invalid draft: {problems!r}", run_id=rid)
        raise RuntimeError(f"{NODE}: assembled an invalid draft: {problems!r}")
    log.info(NODE, f"draft {slug!r} assembled (status draft)", run_id=rid)
    return {"draft_contract": draft, "visited": [NODE]}


register_research_node(NODE, contract_draft)
