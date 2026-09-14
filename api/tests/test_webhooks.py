"""Webhook + analytics trigger contracts (spec C3/C5).

Offline tests: HMAC signature verification, deduplication, event dispatch,
and unknown-type no-op.  No network, no Fourthwall MCP, no database.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.analytics_trigger import is_triggered_type, trigger_from_event
from api.app.collections_store import CollectionsStore, get_collections_store
from api.app.routers.webhooks import router
from api.app.webhooks import is_duplicate, reset_dedup, verify_signature

SECRET = "test-webhook-secret-1234"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _event(event_id: str = "evt-1", event_type: str = "order.created", **data: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"id": event_id, "type": event_type, "data": data}
    return payload


def _store_with_contract(slug: str = "vibe-coding") -> CollectionsStore:
    tmpdir = Path(tempfile.mkdtemp()) / "collections"
    store = CollectionsStore(tmpdir)
    store.create({
        "collection_id": slug,
        "theme": f"{slug} theme",
        "status": "active",
        "style_archetype": "minimal",
        "illustration_rules": {"line_weight": "thin", "palette": ["#000"], "no_mixed_styles": True},
        "kpi_thresholds": {"min_units": 2, "min_conversion": None, "eval_window_days": 7},
        "created_by": "test",
        "created_at": "2026-09-01T00:00:00Z",
        "approved_at": "2026-09-01T00:00:00Z",
    })
    return store


def _app(store: CollectionsStore, webhook_secret: str = SECRET) -> TestClient:
    import api.app.config as cfg
    # Set the env var and clear the lru_cache so settings picks it up.
    os.environ["FOURTHWALL_WEBHOOK_SECRET"] = webhook_secret
    cfg.get_settings.cache_clear()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_collections_store] = lambda: store
    client = TestClient(app, raise_server_exceptions=False)
    return client


# --------------------------------------------------------------- unit tests

def test_verify_signature_valid() -> None:
    body = b'{"id":"evt-1","type":"order"}'
    assert verify_signature(body, _sign(body), SECRET) is True


def test_verify_signature_wrong_secret() -> None:
    body = b'{"id":"evt-1","type":"order"}'
    assert verify_signature(body, _sign(body), "wrong-secret") is False


def test_verify_signature_empty() -> None:
    assert verify_signature(b"body", "", SECRET) is False
    assert verify_signature(b"body", "sig", "") is False


def test_dedup_first_event_not_duplicate() -> None:
    reset_dedup()
    assert is_duplicate("evt-new-1") is False


def test_dedup_second_event_is_duplicate() -> None:
    reset_dedup()
    assert is_duplicate("evt-dup-1") is False
    assert is_duplicate("evt-dup-1") is True


def test_is_triggered_type_order() -> None:
    assert is_triggered_type("order") is True
    assert is_triggered_type("ORDER") is True
    assert is_triggered_type("checkout") is True
    assert is_triggered_type("order.created") is True
    assert is_triggered_type("order.paid") is True


def test_is_triggered_type_unknown() -> None:
    assert is_triggered_type("refund") is False
    assert is_triggered_type("product.updated") is False


# ----------------------------------------------------------- trigger tests

def test_trigger_from_event_dispatches_order() -> None:
    store = _store_with_contract()
    event = _event("evt-dispatch-1", "order.created", total=32.0, status="paid")
    result = trigger_from_event(event, store)
    assert result["processed"] is True
    assert result["collection_id"] == "vibe-coding"
    assert result["event_id"] == "evt-dispatch-1"


def test_trigger_from_event_unknown_type_noop() -> None:
    store = _store_with_contract()
    event = _event("evt-unknown-1", "refund.created")
    result = trigger_from_event(event, store)
    assert result["processed"] is False
    assert result["collection_id"] is None


def test_trigger_from_event_with_collection_mapping() -> None:
    store = _store_with_contract("retro-wave")
    event = _event("evt-map-1", "order.created", collection_id="retro-wave", total=20.0)
    result = trigger_from_event(event, store)
    assert result["processed"] is True
    assert result["collection_id"] == "retro-wave"


# ----------------------------------------------------------- API tests

def test_webhook_bad_signature_403() -> None:
    store = _store_with_contract()
    client = _app(store)
    body = json.dumps(_event("evt-sig-1")).encode()
    resp = client.post(
        "/api/webhooks/fourthwall",
        content=body,
        headers={"X-Webhook-Signature": "bad-sig"},
    )
    assert resp.status_code == 403
    assert "invalid webhook signature" in resp.json()["detail"]


def test_webhook_valid_event_accepted() -> None:
    reset_dedup()
    store = _store_with_contract()
    client = _app(store)
    event = _event("evt-accept-1", "order.created", total=62.0)
    body = json.dumps(event).encode()
    resp = client.post(
        "/api/webhooks/fourthwall",
        content=body,
        headers={"X-Webhook-Signature": _sign(body)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["event_id"] == "evt-accept-1"
    assert data["processed"] is True


def test_webhook_duplicate_event() -> None:
    reset_dedup()
    store = _store_with_contract()
    client = _app(store)
    event = _event("evt-dup-api-1", "order.created", total=20.0)
    body = json.dumps(event).encode()
    sig = _sign(body)

    resp1 = client.post("/api/webhooks/fourthwall", content=body, headers={"X-Webhook-Signature": sig})
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "accepted"

    resp2 = client.post("/api/webhooks/fourthwall", content=body, headers={"X-Webhook-Signature": sig})
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate"


def test_webhook_unknown_type_noop() -> None:
    reset_dedup()
    store = _store_with_contract()
    client = _app(store)
    event = _event("evt-noop-1", "refund.created")
    body = json.dumps(event).encode()
    resp = client.post(
        "/api/webhooks/fourthwall",
        content=body,
        headers={"X-Webhook-Signature": _sign(body)},
    )
    assert resp.status_code == 200
    assert resp.json()["processed"] is False


def test_webhook_invalid_json_400() -> None:
    store = _store_with_contract()
    client = _app(store)
    body = b"not-json"
    resp = client.post(
        "/api/webhooks/fourthwall",
        content=body,
        headers={"X-Webhook-Signature": _sign(body)},
    )
    assert resp.status_code == 400
    assert "invalid JSON" in resp.json()["detail"]


def test_webhook_missing_event_id_400() -> None:
    store = _store_with_contract()
    client = _app(store)
    body = json.dumps({"type": "order.created"}).encode()
    resp = client.post(
        "/api/webhooks/fourthwall",
        content=body,
        headers={"X-Webhook-Signature": _sign(body)},
    )
    assert resp.status_code == 400
    assert "missing event id" in resp.json()["detail"]


def test_webhook_checkout_event_dispatches() -> None:
    reset_dedup()
    store = _store_with_contract()
    client = _app(store)
    event = _event("evt-co-1", "checkout.completed", total=32.0)
    body = json.dumps(event).encode()
    resp = client.post(
        "/api/webhooks/fourthwall",
        content=body,
        headers={"X-Webhook-Signature": _sign(body)},
    )
    assert resp.status_code == 200
    assert resp.json()["processed"] is True
    assert resp.json()["collection_id"] == "vibe-coding"
