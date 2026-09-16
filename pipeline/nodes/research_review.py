"""Research node 1 — inspiration review (spec C4).

Inventories the curated input (assets + link refs carried in state by the
caller — the graph never fetches the web) and validates it: empty input is
an error, never a silent pass. No model call; deterministic and cheap.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..collection_graph import RESEARCH_DEFAULT_HITL, register_research_node
from ..runlog import get_logger

NODE = "inspiration_review"


def inspiration_review(
    state: dict[str, Any], config: RunnableConfig = None  # type: ignore[assignment]
) -> dict[str, Any]:
    """Record what the synthesis may draw on; loud when there is nothing."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, RESEARCH_DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})
    log = get_logger(cfg)
    rid = str(cfg.get("thread_id") or "")
    inspiration = state.get("inspiration") or {}
    assets = inspiration.get("assets") or []
    refs = inspiration.get("refs") or []
    if not assets and not refs:
        log.error(NODE, "no inspiration assets or refs in state", run_id=rid)
        return {
            "visited": [NODE],
            "errors": [f"{NODE}: no inspiration assets or refs in state"],
        }
    summary = {"asset_count": len(assets), "ref_count": len(refs)}
    log.info(NODE, f"{len(assets)} assets + {len(refs)} refs under review", run_id=rid)
    return {"inspiration": {**inspiration, "reviewed": summary}, "visited": [NODE]}


register_research_node(NODE, inspiration_review)
