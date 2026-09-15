"""Catalog mirror API (spec C1/C6).

Read-only Fourthwall mirror: list/detail with server-computed price-invariant
status, recent order history, and survivor flags from collection contracts.
Never writes to Fourthwall (C6/CC-2 — no write method may enter this router).
Degraded reads surface as explicit unavailable payloads (dashboard C5
convention), never fabricated products.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..collections_store import CollectionsStore, get_collections_store
from ..fourthwall.client import FourthwallError, FourthwallReadClient, get_fourthwall_client
from ..rbac import require_role

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))

# Price invariants (product definition — enforced mechanically at the Shelf
# node; this mirror only REPORTS pass/fail, never sets prices).
PRICE_INVARIANTS: dict[str, float] = {"tee": 32.0, "hoodie": 62.0, "mug": 20.0}


def _category_of(raw: dict[str, Any]) -> Optional[str]:
    """Map payload category hints to the invariant table (pure).

    Fourthwall exposes no product-category field (``type`` is only
    STANDARD/GIFT_CARD/UNKNOWN), so the keyword scan also covers the product
    ``name``/``title``/``slug`` — the only place "Tee"/"Hoodie"/"Mug" appears.
    """
    for key in ("category", "product_type", "type", "name", "title", "slug"):
        value = raw.get(key)
        if isinstance(value, str):
            lowered = value.lower()
            if "hoodie" in lowered:
                return "hoodie"
            if "mug" in lowered:
                return "mug"
            if "tee" in lowered or "t-shirt" in lowered or "tshirt" in lowered:
                return "tee"
    return None


def _price_of(raw: dict[str, Any]) -> Optional[float]:
    """Extract a unit price from known payload shapes (pure)."""
    for key in ("price", "price_usd", "unit_price"):
        value = raw.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    variants = raw.get("variants")
    if isinstance(variants, list) and variants:
        first = variants[0] if isinstance(variants[0], dict) else {}
        return _price_of(first)
    return None


def invariant_status(raw: dict[str, Any]) -> dict[str, Any]:
    """Server-side price-invariant verdict (pure).

    pass/fail only when BOTH category and price are known; otherwise an
    explicit unmapped/unknown flag — never a guessed rule (refinement rule).
    """
    category = _category_of(raw)
    if category is None:
        return {"status": "unmapped", "expected": None, "actual": _price_of(raw),
                "reason": "category unmapped — no invariant rule applies"}
    price = _price_of(raw)
    expected = PRICE_INVARIANTS[category]
    if price is None:
        return {"status": "unknown", "expected": expected, "actual": None,
                "reason": "no price in Fourthwall payload"}
    if abs(price - expected) < 0.005:
        return {"status": "pass", "expected": expected, "actual": price, "reason": None}
    return {"status": "fail", "expected": expected, "actual": price,
            "reason": f"{category} must be ${expected:g}"}


def _survivor_map(store: CollectionsStore) -> dict[str, str]:
    """product_id → retired collection slug (A9 survivor exception)."""
    mapping: dict[str, str] = {}
    try:
        records = store.list(status="retired")
    except Exception:  # noqa: BLE001 - catalog degrades, never 500s on YAML
        return mapping
    for record in records:
        slug = record["contract"]["collection_id"]
        for product_id in record["contract"].get("survivor_products") or []:
            mapping[str(product_id)] = slug
    return mapping


def _present(product: dict[str, Any], survivors: dict[str, str]) -> dict[str, Any]:
    return {
        "id": product.get("id"),
        "title": product.get("title") or product.get("name"),
        "status": product.get("status"),
        "category": _category_of(product),
        "price": _price_of(product),
        "invariant": invariant_status(product),
        "survivor_of": survivors.get(str(product.get("id"))),
        "raw": product,
    }


@router.get("")
def list_catalog(
    actor: Actor = ReadAllowed,
    client: FourthwallReadClient = Depends(get_fourthwall_client),
    store: CollectionsStore = Depends(get_collections_store),
) -> dict[str, Any]:
    try:
        products = client.list_products()
    except FourthwallError as exc:
        return {"items": [], "source": "unavailable", "error": str(exc)}
    survivors = _survivor_map(store)
    raws = [p.model_dump() for p in products]
    return {"items": [_present(raw, survivors) for raw in raws], "source": "live", "error": None}


@router.get("/{product_id}")
def get_catalog_product(
    product_id: str,
    actor: Actor = ReadAllowed,
    client: FourthwallReadClient = Depends(get_fourthwall_client),
    store: CollectionsStore = Depends(get_collections_store),
) -> dict[str, Any]:
    try:
        product = client.get_product(product_id)
    except FourthwallError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    raw = product.model_dump()
    try:
        orders = [o.model_dump() for o in client.list_orders(limit=20)]
    except FourthwallError:
        orders = []
    return {
        **_present(raw, _survivor_map(store)),
        # Shop-wide recents: per-product attribution lands when the FW order
        # schema confirms line items (stated, not guessed).
        "order_history": orders,
        "order_history_scope": "shop-wide recents",
    }
