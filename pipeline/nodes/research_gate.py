"""Research node 5 — collection gate (spec C4).

``interrupt()`` with the draft payload (style directives, board ref,
completeness gaps) before anything reaches the collections lifecycle.
Resume carries the CEO decision: approve → draft passes through;
edit-and-approve (``contract`` override) → merged deterministically, with
model-suggested fields never overriding CEO edits; reject → terminal
recorded rejection. Gate defaults ON (RESEARCH_DEFAULT_HITL); flag off
(tests/parity) defaults to NOT approved — creative decisions are never
granted without review.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..collection_graph import RESEARCH_DEFAULT_HITL, register_research_node
from ..runlog import get_logger

NODE = "collection_gate"


def collection_gate(
    state: dict[str, Any], config: RunnableConfig = None  # type: ignore[assignment]
) -> dict[str, Any]:
    """Node 5 implementation: gate the draft, stay draft either way."""
    cfg = (config or {}).get("configurable") or {}
    draft = state.get("draft_contract") or {}
    board = state.get("board") or {}
    log = get_logger(cfg)
    rid = str(cfg.get("thread_id") or "")
    decision: dict[str, Any] = {
        "approved": False,
        "draft_collection_id": draft.get("collection_id"),
        "board_version": board.get("board_version"),
    }
    if cfg.get("hitl", {}).get(NODE, RESEARCH_DEFAULT_HITL[NODE]):
        log.info(NODE, "awaiting CEO decision on the draft", run_id=rid)
        answer = interrupt(
            {
                "node": NODE,
                "status": "awaiting_approval",
                "draft": draft,
                "board": {"file_ref": board.get("file_ref"),
                          "board_version": board.get("board_version")},
            }
        )
        if isinstance(answer, dict):
            decision["approved"] = bool(answer.get("approved"))
            if answer.get("note"):
                decision["note"] = answer["note"]
            override = answer.get("contract")
            if isinstance(override, dict) and override:
                merged = {**draft, **override}
                # The draft's identity never changes under edit-and-approve.
                merged["collection_id"] = draft.get("collection_id")
                merged["status"] = "draft"
                from .contract import validate_contract

                problems = validate_contract(merged)
                if problems:
                    raise ValueError(
                        f"{NODE}: edited contract is invalid: {problems!r}")
                decision["edited_contract"] = merged
        log.info(NODE, f"decision recorded: approved={decision['approved']}", run_id=rid)
    else:
        log.info(NODE, "gate off — defaulting to not approved", run_id=rid)
    return {"gate_decision": decision, "visited": [NODE]}


register_research_node(NODE, collection_gate)
