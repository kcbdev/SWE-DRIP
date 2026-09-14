"""Catalog mirror API contracts (offline — fake FW client + tmp collections)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.collections_store import CollectionsStore, get_collections_store
from api.app.fourthwall.client import FourthwallError, FourthwallReadClient
from api.app.routers import catalog as catalog_router
from api.app.routers.catalog import get_fourthwall_client, invariant_status
from api.tests.test_collections_store import _draft


def _product(pid: str, **fields: Any) -> Any:
    from api.app.fourthwall.client import Product

    return Product.model_validate({"id": pid, **fields})


class FakeClient:
    def __init__(self, products: Optional[list] = None, broken: bool = False) -> None:
        self.products = products if products is not None else [
            _product("fw-tee", title="Vibe Tee", status="DRAFT", category="tee", price=32),
            _product("fw-hoodie", title="Vibe Hoodie", status="DRAFT", category="hoodie", price=70),
            _product("fw-mug", title="Vibe Mug", status="DRAFT", category="mug", price=20),
            _product("fw-weird", title="Mystery", status="DRAFT", price=10),
        ]
        self.broken = broken

    def list_products(self, **kwargs: Any) -> list:
        if self.broken:
            raise FourthwallError("shop unreachable")
        return self.products

    def get_product(self, product_id: str) -> Any:
        if self.broken:
            raise FourthwallError("shop unreachable")
        for product in self.products:
            if product.id == product_id:
                return product
        raise FourthwallError(f"unknown product {product_id}")

    def list_orders(self, **kwargs: Any) -> list:
        if self.broken:
            raise FourthwallError("shop unreachable")
        from api.app.fourthwall.client import Order

        return [Order.model_validate({"id": "o-1", "status": "paid", "total": 32.0})]


class Harness:
    def __init__(self, role: str = ROLE_VIEWER, client: Optional[FakeClient] = None,
                 retired_with: Optional[list[str]] = None) -> None:
        import tempfile

        self.client = client or FakeClient()
        self.store = CollectionsStore(Path(tempfile.mkdtemp()) / "collections")
        if retired_with is not None:
            record = self.store.create(_draft("vibe-coding", status="draft"))
            self.store.transition("vibe-coding", to_status="active", stamp={"approved_at": "t"})
            self.store.transition("vibe-coding", to_status="retired",
                                  stamp={"retired_at": "t", "survivor_products": retired_with})
        app = FastAPI()
        app.include_router(catalog_router.router)
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "op@x.y", role)
        app.dependency_overrides[get_fourthwall_client] = lambda: self.client
        app.dependency_overrides[get_collections_store] = lambda: self.store
        self.client_app = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------- invariants


def test_invariant_pass_fail_per_type() -> None:
    assert invariant_status({"category": "tee", "price": 32})["status"] == "pass"
    assert invariant_status({"category": "hoodie", "price": 70})["status"] == "fail"
    assert invariant_status({"category": "hoodie", "price": 70})["expected"] == 62.0
    assert invariant_status({"category": "mug", "price": 20})["status"] == "pass"


def test_unknown_category_is_flagged_never_guessed() -> None:
    verdict = invariant_status({"price": 10})
    assert verdict["status"] == "unmapped"
    assert "unmapped" in verdict["reason"]


def test_missing_price_is_unknown() -> None:
    assert invariant_status({"category": "tee"})["status"] == "unknown"


# --------------------------------------------------------------------- API


def test_list_mirror_with_invariants_and_survivors() -> None:
    h = Harness(retired_with=["fw-tee"])
    body = h.client_app.get("/api/catalog").json()
    assert body["source"] == "live" and body["error"] is None
    by_id = {item["id"]: item for item in body["items"]}
    assert by_id["fw-tee"]["invariant"]["status"] == "pass"
    assert by_id["fw-hoodie"]["invariant"]["status"] == "fail"
    assert by_id["fw-weird"]["invariant"]["status"] == "unmapped"
    assert by_id["fw-tee"]["survivor_of"] == "vibe-coding"  # A9 flagged live
    assert by_id["fw-hoodie"]["survivor_of"] is None


def test_list_degraded_shape() -> None:
    body = Harness(client=FakeClient(broken=True)).client_app.get("/api/catalog").json()
    assert body == {"items": [], "source": "unavailable", "error": "shop unreachable"}


def test_detail_with_order_history() -> None:
    body = Harness().client_app.get("/api/catalog/fw-tee").json()
    assert body["invariant"]["status"] == "pass"
    assert body["order_history"][0]["id"] == "o-1"
    assert body["order_history_scope"] == "shop-wide recents"


def test_detail_degraded_is_502() -> None:
    h = Harness(client=FakeClient(broken=True))
    response = h.client_app.get("/api/catalog/fw-tee")
    assert response.status_code == 502


def test_catalog_role_matrix() -> None:
    assert Harness(role=ROLE_VIEWER).client_app.get("/api/catalog").status_code == 200
    assert Harness(role=ROLE_ADMIN).client_app.get("/api/catalog/fw-tee").status_code == 200
    app = FastAPI()
    app.include_router(catalog_router.router)
    assert TestClient(app).get("/api/catalog").status_code == 401


def test_router_has_no_write_methods() -> None:
    paths = {route.path for route in catalog_router.router.routes}
    assert paths == {"/api/catalog", "/api/catalog/{product_id}"}
    methods = {m for route in catalog_router.router.routes for m in route.methods}
    assert methods == {"GET"}  # CC-2: reads only
