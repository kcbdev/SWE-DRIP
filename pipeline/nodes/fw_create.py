"""Node 9 — Fourthwall product create, DRAFT-only (spec C2/C4/C7).

Calls Fourthwall through an INJECTED client interface
(``config["configurable"]["fw_client"]``) — no MCP client lives here; the
fourthwall-integration spec implements the interface. A live call sits behind
the explicit ``fw_live`` config flag (default off); tests inject a mock with
the flag on. This phase may only create DRAFT/unpublished products:

- the outgoing payload hardcodes ``state: "DRAFT"``,
- a client response claiming anything public is LOUD (``ValueError``),
- no code path in this module can emit ``PUBLIC`` (asserted in tests).

Price comes from the single ``PRICE_INVARIANTS`` source (``shelf.py``), never
a literal. Product type defaults to ``"tee"`` via config override
(``product_type``); the price is always the invariant for that type.
"""

from __future__ import annotations

from typing import Any, Protocol

from langgraph.types import RunnableConfig, interrupt

from ..graph import DEFAULT_HITL, register_node
from ..state import RunState
from .shelf import PRICE_INVARIANTS

NODE = "fw_create"

DRAFT_STATE = "DRAFT"


class FourthwallClient(Protocol):
    """Interface implemented by the fourthwall-integration client (Phase 5)."""

    def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]: ...


def fw_create(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Node 9 implementation: build the draft, send only when flagged live."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})

    copy = state.get("listing_copy") or {}
    spec = state.get("design_spec") or {}
    render = state.get("render_result") or {}
    if not copy or not spec or not render:
        return {
            "fw_product": {},
            "visited": [NODE],
            "errors": [f"{NODE}: missing copy/spec/render — nothing to draft"],
        }

    product_type = cfg.get("product_type") or "tee"
    if product_type not in PRICE_INVARIANTS:
        return {
            "fw_product": {},
            "visited": [NODE],
            "errors": [f"{NODE}: unknown product_type {product_type!r}"],
        }
    payload = {
        "title": copy.get("title", ""),
        "description": copy.get("description", ""),
        "tags": copy.get("tags", []),
        "product_type": product_type,
        "price": PRICE_INVARIANTS[product_type],
        "state": DRAFT_STATE,  # phase lock — DRAFT only, never PUBLIC
        "render_file": render.get("file_url", ""),
        "collection_id": state.get("collection_id", ""),
    }

    client = cfg.get("fw_client")
    if client is None:
        return {
            "fw_product": {},
            "visited": [NODE],
            "errors": [f"{NODE}: no fw_client in config['configurable']"],
        }
    if not cfg.get("fw_live"):
        return {
            "fw_product": {**payload, "sent": False},
            "visited": [NODE],
            "errors": [f"{NODE}: live FW disabled this phase — draft not sent"],
        }

    response = client.create_draft(payload)
    if not isinstance(response, dict) or response.get("state", DRAFT_STATE) != DRAFT_STATE:
        raise ValueError(
            f"{NODE}: FW client returned a non-DRAFT product {response!r} — "
            "PUBLIC is unreachable in this phase"
        )
    product = {**payload, **response, "state": DRAFT_STATE, "sent": True}
    return {"fw_product": product, "visited": [NODE]}


register_node(NODE, fw_create)
