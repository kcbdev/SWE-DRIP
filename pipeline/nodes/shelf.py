"""Node 11 — shelf: pricing invariants + collection assignment (spec C10).

Founder-locked price invariants live in ONE module constant here
(``PRICE_INVARIANTS`` — PBI-014 refinement rule: no per-node literals; the
FW-create node reads this same constant to price drafts). A mismatch REJECTS
the run: ``shelf_result.accepted`` is False with itemized errors — recorded,
not raised, so the rejection itself stays inspectable for traceability
(PBI-028). Collection assignment requires status exactly ``active``
(draft → not yet activatable; retired → gone; both reject).
"""

from __future__ import annotations

from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..graph import DEFAULT_HITL, register_node
from ..state import RunState

NODE = "shelf"

# Founder-locked price invariants ($32 tee / $62 hoodie / $20 mug).
# Change requires founder approval via spec change — never a code tweak.
PRICE_INVARIANTS: dict[str, float] = {
    "tee": 32.0,
    "hoodie": 62.0,
    "mug": 20.0,
}


def check_price(product_type: Any, price: Any) -> list[str]:
    """Mechanical invariant check. Returns error strings (empty = valid)."""
    if product_type not in PRICE_INVARIANTS:
        return [f"unknown product_type {product_type!r} (must be one of {sorted(PRICE_INVARIANTS)!r})"]
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        return [f"price must be a number, got {price!r}"]
    expected = PRICE_INVARIANTS[product_type]
    if round(float(price), 2) != expected:
        return [f"price {price} violates invariant ${expected:g} {product_type}"]
    return []


def check_contract(contract: dict[str, Any]) -> list[str]:
    """Collection must be active and non-retired."""
    if not contract:
        return ["no collection contract in state"]
    status = contract.get("status")
    if status == "retired":
        return [f"collection {contract.get('collection_id')!r} is retired"]
    if status != "active":
        return [f"collection {contract.get('collection_id')!r} is not active (status={status!r})"]
    return []


def shelf(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Node 11 implementation: mechanical gate, rejection recorded."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})

    product = state.get("fw_product") or {}
    contract = state.get("collection_contract") or {}
    errors: list[str] = []
    if not product:
        errors.append(f"{NODE}: no FW product in state")
    else:
        errors.extend(check_price(product.get("product_type"), product.get("price")))
    errors.extend(check_contract(contract))

    result = {
        "accepted": not errors,
        "product_type": product.get("product_type"),
        "price": product.get("price"),
        "collection_id": contract.get("collection_id"),
        "errors": errors,
    }
    output: dict[str, Any] = {"shelf_result": result, "visited": [NODE]}
    if errors:
        output["errors"] = [f"{NODE}: rejected run: {'; '.join(errors)}"]
    return output


register_node(NODE, shelf)
