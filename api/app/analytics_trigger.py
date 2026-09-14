"""Shared analytics trigger — invoked by both webhooks and scheduled catch-up pulls (C3).

Dispatches order/checkout events to the KPI math in ``analytics.py`` and
returns what was recomputed.  Both entry paths (webhook POST and scheduled
poll) funnel through this module so the analytics update logic lives in one
place.  This module never writes to Fourthwall (C6 anti-pattern).
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Optional

from .analytics import collection_kpi
from .collections_schema import CollectionContract
from .collections_store import CollectionsStore
from .fourthwall.client import FourthwallError, FourthwallReadClient

logger = logging.getLogger(__name__)

# Event types that trigger an analytics recomputation.
_TRIGGER_TYPES = {"order", "checkout", "order.created", "order.paid", "checkout.completed"}


def is_triggered_type(event_type: str) -> bool:
    """Return True if this event type should trigger a KPI recomputation."""
    return event_type.lower() in _TRIGGER_TYPES


def trigger_from_event(
    event: dict[str, Any],
    store: CollectionsStore,
    *,
    client: Optional[FourthwallReadClient] = None,
    now: Optional[dt.datetime] = None,
) -> dict[str, Any]:
    """Process a single Fourthwall event and recompute KPI for affected collections.

    When a *client* is provided the trigger fetches the full order history
    (C3: "triggers an Analytics run") before computing KPI.  Without a client
    (e.g. in tests or when Fourthwall is unreachable) it falls back to a
    single synthetic order extracted from the event — degraded but non-blocking.

    Returns a summary dict with:
      - ``processed``: True if KPI was recomputed (trigger type matched)
      - ``collection_id``: which collection was updated (or None)
      - ``kpi``: the recomputed KPI payload (or None)
      - ``event_type``: the original event type
      - ``event_id``: the original event id
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    event_type = str(event.get("type", "")).lower()
    event_id = str(event.get("id", "unknown"))

    if not is_triggered_type(event_type):
        logger.debug("event %s type=%r not a trigger type — no-op", event_id, event_type)
        return {
            "processed": False,
            "collection_id": None,
            "kpi": None,
            "event_type": event_type,
            "event_id": event_id,
        }

    # Determine which collection this event belongs to.
    collection_id = _extract_collection_id(event)

    # If no collection mapping, try all active collections.
    try:
        active_records = store.list(status="active")
    except Exception:
        logger.warning("event %s: failed to list active collections — skipping", event_id, exc_info=True)
        active_records = []

    if collection_id:
        records = [r for r in active_records if r["contract"].get("collection_id") == collection_id]
    else:
        records = active_records

    if not records:
        logger.debug("event %s: no matching active collection — nothing to recompute", event_id)
        return {
            "processed": False,
            "collection_id": collection_id,
            "kpi": None,
            "event_type": event_type,
            "event_id": event_id,
        }

    # Fetch full order history when a client is available (C3: full Analytics run).
    orders = _fetch_orders(client, event) if client else _event_to_orders(event, collection_id)

    # Recompute KPI for each affected collection.
    kpi_results: list[dict[str, Any]] = []
    for record in records:
        raw = {k: v for k, v in record["contract"].items() if k != "slug"}
        contract = CollectionContract.model_validate(raw)
        result = collection_kpi(orders, contract, now)
        kpi_results.append(result)

    primary = kpi_results[0] if kpi_results else None
    return {
        "processed": True,
        "collection_id": primary["collection_id"] if primary else collection_id,
        "kpi": primary,
        "event_type": event_type,
        "event_id": event_id,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_collection_id(event: dict[str, Any]) -> Optional[str]:
    """Best-effort extraction of collection_id from event payload."""
    data = event.get("data")
    if isinstance(data, dict):
        for key in ("collection_id", "collection", "slug"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
        # Try product metadata for collection mapping.
        product = data.get("product")
        if isinstance(product, dict):
            for key in ("collection_id", "collection", "slug"):
                value = product.get(key)
                if isinstance(value, str) and value:
                    return value
    return None


def _fetch_orders(client: FourthwallReadClient, event: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch full order history from Fourthwall (C3: full Analytics run).

    Falls back to synthetic single-order on Fourthwall read errors so the
    webhook never fails hard on a transient upstream issue.
    """
    try:
        orders = client.list_orders(limit=1000)
        return [o.model_dump() for o in orders]
    except FourthwallError:
        logger.warning(
            "event %s: Fourthwall read failed — falling back to synthetic order",
            event.get("id", "unknown"),
            exc_info=True,
        )
        collection_id = _extract_collection_id(event)
        return _event_to_orders(event, collection_id or "unknown")


def _event_to_orders(event: dict[str, Any], collection_id: str) -> list[dict[str, Any]]:
    """Convert a webhook event into a synthetic order dict for degraded-mode KPI."""
    data = event.get("data", {})
    if not isinstance(data, dict):
        data = {}

    # Extract the real order ID from event data, not the event id.
    order_id = data.get("order_id") or data.get("id") or event.get("id", "unknown")
    status = data.get("status", "paid")
    total = data.get("total", data.get("price", 0))
    created = event.get("created_at", data.get("created_at", dt.datetime.now(dt.timezone.utc).isoformat()))

    return [{
        "id": str(order_id),
        "status": str(status),
        "total": float(total) if isinstance(total, (int, float)) else 0.0,
        "created_at": str(created),
        "collection_id": collection_id,
    }]
