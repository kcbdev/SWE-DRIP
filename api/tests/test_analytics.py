"""Analytics API contracts (offline — fake FW client + tmp collections)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.analytics import (
    collection_kpi,
    kpi_series,
    overview_revenue,
    retirement_recommendation,
    units_in_window,
    revenue_in_window,
)
from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.collections_schema import CollectionContract, KpiThresholds
from api.app.collections_store import CollectionsStore, get_collections_store
from api.app.fourthwall.client import FourthwallError, FourthwallReadClient, Order
from api.app.routers.analytics import get_fourthwall_client, router


def _order(order_id: str, price: float, created: str = "2026-09-10T10:00:00Z") -> dict[str, Any]:
    return {"id": order_id, "status": "paid", "total": price, "created_at": created}


def _contract(slug: str, **overrides: Any) -> CollectionContract:
    base: dict[str, Any] = {
        "collection_id": slug,
        "theme": f"{slug} theme",
        "status": "active",
        "style_archetype": "minimal",
        "illustration_rules": {"line_weight": "thin", "palette": ["#000"], "no_mixed_styles": True},
        "kpi_thresholds": {"min_units": 2, "min_conversion": None, "eval_window_days": 7},
        "created_by": "test",
        "created_at": "2026-09-01T00:00:00Z",
        "approved_at": "2026-09-01T00:00:00Z",
    }
    base.update(overrides)
    return CollectionContract(**base)


class FakeClient:
    def __init__(self, orders: Optional[list[dict[str, Any]]] = None, broken: bool = False) -> None:
        self.orders = orders or []
        self.broken = broken

    def list_products(self, **kwargs: Any) -> list:
        if self.broken:
            raise FourthwallError("shop unreachable")
        return []

    def list_orders(self, **kwargs: Any) -> list:
        if self.broken:
            raise FourthwallError("shop unreachable")
        return [Order.model_validate(o) for o in self.orders]


class Harness:
    def __init__(self, role: str = ROLE_VIEWER, client: Optional[FakeClient] = None,
                 contract: Optional[CollectionContract] = None) -> None:
        import tempfile
        self.client = client or FakeClient()
        self.store = CollectionsStore(Path(tempfile.mkdtemp()) / "collections")
        if contract is not None:
            self.store.create(contract.model_dump())
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "op@x.y", role)
        app.dependency_overrides[get_fourthwall_client] = lambda: self.client
        app.dependency_overrides[get_collections_store] = lambda: self.store
        self.client_app = TestClient(app, raise_server_exceptions=False)


NOW = dt.datetime(2026, 9, 14, 12, 0, 0, tzinfo=dt.timezone.utc)


# --------------------------------------------------------------- pure math


def test_units_in_window_counts() -> None:
    orders = [_order("o-1", 32, "2026-09-14T08:00:00Z"), _order("o-2", 62, "2026-09-12T00:00:00Z")]
    assert units_in_window(orders, 7, NOW) == 2
    assert units_in_window(orders, 1, NOW) == 1


def test_revenue_in_window_sums() -> None:
    orders = [_order("o-1", 32, "2026-09-14T08:00:00Z"), _order("o-2", 62, "2026-09-12T00:00:00Z")]
    assert revenue_in_window(orders, 7, NOW) == 94.0


def test_kpi_series_includes_windows() -> None:
    contract = _contract("vibe-coding")
    result = kpi_series([], contract.kpi_thresholds, NOW)
    windows = [s["window_days"] for s in result["series"]]
    assert 7 in windows and 30 in windows
    assert result["thresholds"]["min_units"] == 2


def test_collection_kpi_summary() -> None:
    orders = [_order("o-1", 32)]
    contract = _contract("vibe-coding")
    result = collection_kpi(orders, contract, NOW)
    assert result["summary"]["units_in_eval_window"] == 1
    assert result["summary"]["below_min_units"] is True  # 1 < 2


def test_retirement_recommendation_present_when_below() -> None:
    contract = _contract("vibe-coding", approved_at="2026-09-01T00:00:00Z")
    orders = [_order("o-1", 32)]
    rec = retirement_recommendation(orders, contract, NOW)
    assert rec is not None
    assert rec["verdict"] == "retirement_recommended"
    assert rec["units"] == 1
    assert rec["min_units"] == 2


def test_retirement_recommendation_absent_when_met() -> None:
    contract = _contract("vibe-coding", approved_at="2026-09-01T00:00:00Z")
    orders = [_order("o-1", 32), _order("o-2", 62)]
    rec = retirement_recommendation(orders, contract, NOW)
    assert rec is None


def test_retirement_recommendation_absent_when_window_not_elapsed() -> None:
    contract = _contract("vibe-coding", approved_at="2026-09-10T00:00:00Z")
    orders = [_order("o-1", 32)]
    rec = retirement_recommendation(orders, contract, NOW)
    assert rec is None


def test_retirement_recommendation_absent_when_not_active() -> None:
    contract = _contract("vibe-coding", status="draft", approved_at="2026-09-01T00:00:00Z")
    rec = retirement_recommendation([], contract, NOW)
    assert rec is None


def test_overview_revenue() -> None:
    orders = [_order("o-1", 32), _order("o-2", 20)]
    result = overview_revenue(orders, NOW)
    assert result["revenue_12m"] == 52.0
    assert result["units_12m"] == 2


# --------------------------------------------------------------------- API


def test_collection_kpi_endpoint() -> None:
    contract = _contract("vibe-coding")
    h = Harness(client=FakeClient(orders=[_order("o-1", 32)]), contract=contract)
    body = h.client_app.get("/api/analytics/collections/vibe-coding").json()
    assert body["summary"]["units_in_eval_window"] == 1
    assert body["summary"]["below_min_units"] is True


def test_collection_kpi_404() -> None:
    body = Harness().client_app.get("/api/analytics/collections/missing")
    assert body.status_code == 404


def test_overview_endpoint() -> None:
    h = Harness(client=FakeClient(orders=[_order("o-1", 32)]), contract=_contract("vibe-coding"))
    body = h.client_app.get("/api/analytics/overview").json()
    assert body["revenue_12m"] == 32.0


def test_recommendation_endpoint_below() -> None:
    contract = _contract("vibe-coding", approved_at="2026-09-01T00:00:00Z")
    h = Harness(client=FakeClient(orders=[_order("o-1", 32)]), contract=contract)
    body = h.client_app.get("/api/analytics/collections/vibe-coding/recommendation").json()
    assert body["verdict"] == "retirement_recommended"


def test_recommendation_endpoint_no_rec() -> None:
    contract = _contract("vibe-coding", approved_at="2026-09-10T00:00:00Z")
    h = Harness(client=FakeClient(orders=[_order("o-1", 32)]), contract=contract)
    body = h.client_app.get("/api/analytics/collections/vibe-coding/recommendation").json()
    assert body["verdict"] == "no_recommendation"


def test_degraded_read_returns_empty_series() -> None:
    h = Harness(client=FakeClient(broken=True))
    body = h.client_app.get("/api/analytics/overview").json()
    assert body["revenue_12m"] == 0.0


def test_analytics_role_matrix() -> None:
    assert Harness(role=ROLE_VIEWER).client_app.get("/api/analytics/overview").status_code == 200
    assert Harness(role=ROLE_ADMIN).client_app.get("/api/analytics/overview").status_code == 200
    app = FastAPI()
    app.include_router(router)
    assert TestClient(app).get("/api/analytics/overview").status_code == 401
