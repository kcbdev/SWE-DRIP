"""Analytics router (spec C2/C4/C6).

Read-only KPI endpoints sourced through Fourthwall reads + collection contracts.
C6: never writes to Fourthwall; never mutates collection status (C4 anti-pattern).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from ..analytics import collection_kpi, overview_revenue, retirement_recommendation
from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..collections_schema import CollectionContract
from ..collections_store import CollectionsStore, CollectionNotFound, get_collections_store
from ..fourthwall.client import FourthwallError, FourthwallReadClient, get_fourthwall_client
from ..rbac import require_role

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))


def _all_orders(client: FourthwallReadClient) -> list[dict[str, Any]]:
    try:
        return [o.model_dump() for o in client.list_orders(limit=1000)]
    except FourthwallError:
        return []


@router.get("/overview")
def get_overview(
    actor: Actor = ReadAllowed,
    client: FourthwallReadClient = Depends(get_fourthwall_client),
    store: CollectionsStore = Depends(get_collections_store),
) -> dict[str, Any]:
    import datetime as dt

    now = dt.datetime.now(dt.timezone.utc)
    orders = _all_orders(client)
    try:
        collections = [
            r["contract"] for r in store.list(status="active")
        ]
    except Exception:
        collections = []
    return overview_revenue(orders, now, collections=collections)


@router.get("/collections/{collection_id}")
def get_collection_kpi(
    collection_id: str,
    actor: Actor = ReadAllowed,
    client: FourthwallReadClient = Depends(get_fourthwall_client),
    store: CollectionsStore = Depends(get_collections_store),
) -> dict[str, Any]:
    import datetime as dt

    now = dt.datetime.now(dt.timezone.utc)
    try:
        record = store.get(collection_id)
    except (CollectionNotFound, KeyError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"collection {collection_id} not found")
    raw = {k: v for k, v in record["contract"].items() if k != "slug"}
    contract = CollectionContract.model_validate(raw)
    orders = _all_orders(client)
    return collection_kpi(orders, contract, now)


@router.get("/collections/{collection_id}/recommendation")
def get_retirement_recommendation(
    collection_id: str,
    actor: Actor = ReadAllowed,
    client: FourthwallReadClient = Depends(get_fourthwall_client),
    store: CollectionsStore = Depends(get_collections_store),
) -> dict[str, Any]:
    import datetime as dt

    now = dt.datetime.now(dt.timezone.utc)
    try:
        record = store.get(collection_id)
    except (CollectionNotFound, KeyError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"collection {collection_id} not found")
    raw = {k: v for k, v in record["contract"].items() if k != "slug"}
    contract = CollectionContract.model_validate(raw)
    orders = _all_orders(client)
    rec = retirement_recommendation(orders, contract, now)
    if rec is None:
        return {
            "collection_id": collection_id,
            "verdict": "no_recommendation",
            "reason": "thresholds met or window not elapsed",
            "note": "Advisory only — no auto-execution.",
        }
    return rec
