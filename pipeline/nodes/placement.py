"""Node 6 — placement & colorway resolution (spec C8).

PURE deterministic function of (collection contract, design type): template
lookup → placement zones + contrast-flagged colorway filtering. NO model calls
(routing maps this node to None). The ``contrast_pass`` flags live in the
contract (set at authoring/calibration time); this node filters by them, it
does not compute contrast itself.

Design-type source: ``design_spec.design_type`` → ``brief.design_type`` →
``config["configurable"]["design_type"]``. It is NOT inferred from subject
text — inferring creative facts would bypass the locked contract
(anti-pattern). Missing type or template is recorded, never crash-inducing.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..graph import DEFAULT_HITL, register_node
from ..runlog import get_logger
from ..state import RunState

NODE = "placement"


def resolve_placement(contract: dict[str, Any], design_type: str) -> dict[str, Any]:
    """Pure resolver: contract + design type → zones + valid colorways."""
    templates = contract.get("placement_templates") or []
    match = next((t for t in templates if t.get("design_type") == design_type), None)
    if match is None:
        raise ValueError(f"no placement template for design_type {design_type!r}")
    try:
        zones = {"front": match["front"], "back": match["back"], "sleeve": match["sleeve"]}
    except KeyError as exc:
        raise ValueError(f"placement template for {design_type!r} missing zone {exc}") from None
    colorways = [
        entry["base"]
        for entry in (contract.get("garment_colorways") or [])
        if isinstance(entry, dict) and entry.get("contrast_pass") is True and entry.get("base")
    ]
    return {"design_type": design_type, "zones": zones, "colorways_valid": colorways}


def placement(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Node 6 implementation: resolve zones, fill render colorways."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})

    contract = state.get("collection_contract") or {}
    log = get_logger(cfg)
    rid = str(cfg.get("thread_id") or "")
    if not contract:
        log.error(NODE, "no collection contract in state", run_id=rid)
        return {"placement": {}, "visited": [NODE], "errors": [f"{NODE}: no collection contract in state"]}
    spec = state.get("design_spec") or {}
    brief = state.get("brief") or {}
    design_type = spec.get("design_type") or brief.get("design_type") or cfg.get("design_type")
    if not design_type:
        log.error(NODE, "no design_type (spec, brief, or config) — not inferring one", run_id=rid)
        return {
            "placement": {},
            "visited": [NODE],
            "errors": [f"{NODE}: no design_type (spec, brief, or config) — not inferring one"],
        }
    try:
        resolved = resolve_placement(contract, design_type)
    except ValueError as exc:
        log.error(NODE, str(exc), run_id=rid)
        return {"placement": {}, "visited": [NODE], "errors": [f"{NODE}: {exc}"]}

    log.info(NODE, f"{design_type}: zones {resolved['zones']} "
                   f"({len(resolved['colorways_valid'])} valid colorways)", run_id=rid)
    output: dict[str, Any] = {"placement": resolved["zones"], "visited": [NODE]}
    render = state.get("render")
    if render:
        output["render"] = {**render, "colorways_valid": resolved["colorways_valid"]}
        if state.get("render_result"):
            output["render_result"] = {
                **state["render_result"],
                "colorways_valid": resolved["colorways_valid"],
            }
    return output


register_node(NODE, placement)
