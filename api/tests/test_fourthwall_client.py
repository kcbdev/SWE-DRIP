"""Fourthwall MCP read client contracts (offline — fake session factory, no network)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from api.app.fourthwall.client import (
    FourthwallAuthError,
    FourthwallConfigError,
    FourthwallError,
    FourthwallReadClient,
    FourthwallTimeoutError,
)


def _client(handler, *, token: str = "tok", url: str = "https://mcp.fourthwall.test/mcp") -> FourthwallReadClient:
    async def factory(tool: str, args: dict[str, Any]) -> Any:
        return await handler(tool, args)

    return FourthwallReadClient(url=url, token=token, session_factory=factory)


async def _products(tool: str, args: dict[str, Any]) -> Any:
    assert tool == "list_products"
    assert args == {"limit": 50}
    return {"products": [{"id": "fw-1", "title": "Vibe Tee", "status": "DRAFT", "price": 32}]}


def test_list_products_typed_mapping() -> None:
    (product,) = _client(_products).list_products()
    assert product.id == "fw-1" and product.title == "Vibe Tee" and product.status == "DRAFT"
    assert product.model_extra.get("price") == 32  # unknown fields pass through, typed core stays


async def _detail(tool: str, args: dict[str, Any]) -> Any:
    assert (tool, args) == ("get_product", {"product_id": "fw-1"})
    return {"product": {"id": "fw-1", "title": "Vibe Tee"}}


def test_get_product_unwraps_envelope() -> None:
    assert _client(_detail).get_product("fw-1").title == "Vibe Tee"


async def _orders(tool: str, args: dict[str, Any]) -> Any:
    assert tool == "list_orders"
    return {"orders": [{"id": "o-1", "status": "paid", "total": 32.0, "currency": "USD"}]}


def test_list_orders_typed_mapping() -> None:
    (order,) = _client(_orders).list_orders()
    assert (order.id, order.total, order.currency) == ("o-1", 32.0, "USD")


async def _analytics(tool: str, args: dict[str, Any]) -> Any:
    assert (tool, args) == ("get_analytics", {"metric": "units", "window_days": 30})
    return {"points": [{"t": "2026-09-01", "value": 3}]}


def test_get_analytics_typed_mapping() -> None:
    report = _client(_analytics).get_analytics(metric="units")
    assert report.metric == "units" and report.window_days == 30
    assert report.points[0].value == 3


async def _timeout(tool: str, args: dict[str, Any]) -> Any:
    raise asyncio.TimeoutError("slow server")


def test_timeout_is_explicit() -> None:
    with pytest.raises(FourthwallTimeoutError, match="list_products"):
        _client(_timeout).list_products()


async def _denied(tool: str, args: dict[str, Any]) -> Any:
    raise RuntimeError("401 Unauthorized")


def test_auth_failure_is_explicit() -> None:
    with pytest.raises(FourthwallAuthError):
        _client(_denied).list_products()


async def _boom(tool: str, args: dict[str, Any]) -> Any:
    raise RuntimeError("weird transport glitch")


def test_unknown_failure_is_explicit_never_silent() -> None:
    with pytest.raises(FourthwallError, match="glitch"):
        _client(_boom).list_products()


def test_missing_token_is_loud() -> None:
    with pytest.raises(FourthwallConfigError, match="FOURTHWALL_MCP_TOKEN"):
        _client(_products, token="").list_products()


def test_missing_url_is_loud() -> None:
    with pytest.raises(FourthwallConfigError, match="FOURTHWALL_MCP_URL"):
        _client(_products, url="").list_products()


def test_no_write_methods_exist() -> None:
    client = _client(_products)
    for name in ("create_product", "update_product", "delete_product", "publish", "write"):
        assert not hasattr(client, name)
