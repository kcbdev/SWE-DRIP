"""Fourthwall webhook router (spec C3/C5).

POST /api/webhooks/fourthwall — receives order/checkout events from
Fourthwall.  Authenticates via HMAC-SHA256 (``X-Webhook-Signature`` header),
deduplicates by event id, and dispatches to the shared analytics trigger
module.  Unknown event types are logged and return 200 (no-op).

Scope: no writes to Fourthwall (C6); no direct KPI computation (delegated
to analytics_trigger → analytics).  No polling — this is a push endpoint.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from ..analytics_trigger import trigger_from_event
from ..collections_store import CollectionsStore, get_collections_store
from ..config import get_settings
from ..fourthwall.client import FourthwallReadClient, get_fourthwall_client
from ..webhooks import is_duplicate, verify_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _webhook_secret() -> str:
    """Read the secret from settings (re-evaluated per request for testability)."""
    return get_settings().fourthwall_webhook_secret


def _optional_fourthwall_client() -> Optional[FourthwallReadClient]:
    """Return a Fourthwall read client if MCP env is configured, else None.

    The webhook endpoint must never hard-fail when Fourthwall is unreachable
    — the trigger falls back to degraded mode (synthetic order from event).
    """
    import os
    url = os.environ.get("FOURTHWALL_MCP_URL", "")
    token = os.environ.get("FOURTHWALL_MCP_TOKEN", "")
    if not url or not token:
        return None
    return get_fourthwall_client()


@router.post("/fourthwall")
async def receive_fourthwall_webhook(
    request: Request,
    x_webhook_signature: str = Header(..., alias="X-Webhook-Signature"),
    store: CollectionsStore = Depends(get_collections_store),
) -> dict[str, Any]:
    """Receive a Fourthwall order/checkout webhook.

    Validates the HMAC-SHA256 signature, deduplicates by event id, and
    dispatches triggered event types to the analytics module.
    """
    raw_body = await request.body()

    # --- Signature verification (C5) ---
    secret = _webhook_secret()
    if not verify_signature(raw_body, x_webhook_signature, secret):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid webhook signature",
        )

    # --- Parse event payload ---
    try:
        event = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid JSON payload",
        )

    event_id = str(event.get("id", ""))
    event_type = str(event.get("type", ""))

    if not event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing event id",
        )

    # --- Deduplication (C5) ---
    if is_duplicate(event_id):
        logger.info("webhook event %s (type=%s) duplicate — already processed", event_id, event_type)
        return {"status": "duplicate", "event_id": event_id}

    # --- Dispatch to analytics trigger (C3) ---
    # Attempt a full Fourthwall read for the Analytics run; the trigger
    # falls back to degraded mode on read failure.
    client = _optional_fourthwall_client()
    result = trigger_from_event(event, store, client=client)
    logger.info(
        "webhook event %s (type=%s) processed=%s collection=%s",
        event_id,
        event_type,
        result["processed"],
        result["collection_id"],
    )

    return {
        "status": "accepted",
        "event_id": event_id,
        "event_type": event_type,
        **result,
    }
