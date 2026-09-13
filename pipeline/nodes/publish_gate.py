"""Node 10 — publish gate (spec C2, phase lock C7).

``interrupt()`` before ANY public transition. This phase can NEVER emit a
PUBLIC product: the decision state is hardcoded to ``DRAFT`` however the CEO
answers — the cutover belongs to the fourthwall-integration spec (Phase 5)
and any change here that could set PUBLIC is out of scope (stop + flag for
the cutover ADR). Config flag ``hitl.publish_gate`` controls whether the gate
pauses; flag off (tests/parity) defaults to NOT approved — approvals are
never granted without review. Reject/stop semantics belong to the resume
service (PBI-016); on resume the run continues with the recorded decision.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..graph import DEFAULT_HITL, register_node
from ..state import RunState

NODE = "publish_gate"

# Phase lock: the only product state this node may ever record.
DRAFT_STATE = "DRAFT"


def publish_gate(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Node 10 implementation: gate the PUBLIC transition, stay DRAFT."""
    cfg = (config or {}).get("configurable") or {}
    product = state.get("fw_product") or {}
    qc = state.get("aesthetic_qc") or {}
    tech = state.get("technical_qc") or {}

    decision: dict[str, Any] = {
        "approved": False,
        "state": DRAFT_STATE,  # phase lock — PUBLIC is unreachable from here
        "product_id": product.get("id"),
    }
    if cfg.get("hitl", {}).get(NODE, DEFAULT_HITL[NODE]):
        answer = interrupt(
            {
                "node": NODE,
                "status": "awaiting_approval",
                "product": {
                    "id": product.get("id"),
                    "title": product.get("title"),
                    "state": product.get("state"),
                },
                "aesthetic_qc": {"result": qc.get("result"), "attempts": qc.get("attempts")},
                "technical_qc": {"passed": tech.get("passed")},
            }
        )
        if isinstance(answer, dict):
            decision["approved"] = bool(answer.get("approved"))
            if answer.get("note"):
                decision["note"] = answer["note"]
        # Approved or not, the product stays DRAFT until the Phase 5 cutover.
        decision["state"] = DRAFT_STATE
    return {"publish_decision": decision, "visited": [NODE]}


register_node(NODE, publish_gate)
