"""Fourthwall Platform Open API read client contracts.

Offline: an ``httpx.MockTransport`` captures the exact request (path, params,
Basic auth header) and returns a canned payload — no network, no credentials.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Callable

import httpx
import pytest

from api.app.fourthwall.client import (
    OPEN_API_BASE_URL,
    FourthwallAuthError,
    FourthwallConfigError,
    FourthwallError,
    FourthwallReadClient,
    FourthwallTimeoutError,
)

USER = "fw_api_test@fourthwall.com"
PASSWORD = "test-password"
BASE = "https://api.fourthwall.test"


def _client(handler: Callable[[httpx.Request], httpx.Response], **overrides: Any) -> FourthwallReadClient:
    kwargs: dict[str, Any] = {
        "base_url": BASE,
        "username": USER,
        "password": PASSWORD,
        "transport": httpx.MockTransport(handler),
    }
    kwargs.update(overrides)
    return FourthwallReadClient(**kwargs)


def _json(request: httpx.Request, payload: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, request=request)


# --------------------------------------------------------------- transport


def test_uses_basic_auth_and_expected_paths() -> None:
    seen: list[tuple[str, dict[str, str], str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, dict(request.url.params), request.headers.get("authorization", "")))
        if request.url.path.endswith("/p-1"):
            return _json(request, {"id": "p-1", "name": "Some Tee", "variants": []})
        return _json(request, {"results": [], "total": 0, "page": 0, "size": 50, "totalPages": 0})

    client = _client(handler)
    client.list_products(limit=10)
    client.list_orders(limit=5)
    client.get_product("p-1")

    expected_header = "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    assert seen[0][0] == "/open-api/v1.0/products"
    assert seen[0][1] == {"size": "10"}
    assert seen[1][0] == "/open-api/v1.0/order"
    assert seen[1][1] == {"size": "5"}
    assert seen[2][0] == "/open-api/v1.0/products/p-1"
    assert all(header == expected_header for _, _, header in seen)


def test_default_base_url_is_the_official_host() -> None:
    assert OPEN_API_BASE_URL == "https://api.fourthwall.com"


# ------------------------------------------------------------ normalization


def test_product_flattens_state_and_variant_price() -> None:
    """Live-shaped product: state.type + variants[].unitPrice({value,currency})."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _json(
            request,
            {
                "results": [
                    {
                        "id": "b0b861ca-2318-498f-8d85-b6ddb32d27dd",
                        "name": "EXIT 0 — Terminal Tee",
                        "slug": "exit-0-terminal-tee",
                        "type": "STANDARD",
                        "state": {"type": "AVAILABLE"},
                        "access": {"type": "PUBLIC"},
                        "variants": [
                            {
                                "id": "v-1",
                                "unitPrice": {"value": 32.0, "currency": "USD"},
                                "stock": {"type": "UNLIMITED"},
                            }
                        ],
                        "createdAt": "2026-09-01T10:00:00.000Z",
                    }
                ],
                "total": 7,
                "page": 0,
                "size": 50,
                "totalPages": 1,
            },
        )

    (product,) = _client(handler).list_products()
    assert product.id == "b0b861ca-2318-498f-8d85-b6ddb32d27dd"
    assert product.name == "EXIT 0 — Terminal Tee"
    assert product.status == "AVAILABLE"
    assert product.price == 32.0
    assert product.currency == "USD"
    assert product.type == "STANDARD"
    # Unknown fields pass through — the typed core stays narrow.
    assert product.model_extra.get("access") == {"type": "PUBLIC"}


def test_product_detail_is_not_wrapped_in_an_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json(request, {"id": "p-1", "name": "Some Hoodie", "variants": []})

    assert _client(handler).get_product("p-1").name == "Some Hoodie"


def test_order_flattens_amounts_and_created_at() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json(
            request,
            {
                "results": [
                    {
                        "id": "o-1",
                        "friendlyId": "D3XZFWPP",
                        "status": "CONFIRMED",
                        "amounts": {"total": {"value": 32.0, "currency": "USD"}},
                        "createdAt": "2026-09-10T09:05:36.939Z",
                    }
                ],
                "total": 1,
                "page": 0,
                "size": 50,
                "totalPages": 1,
            },
        )

    (order,) = _client(handler).list_orders()
    assert order.id == "o-1"
    assert order.status == "CONFIRMED"
    assert order.total == 32.0
    assert order.currency == "USD"
    # The KPI window math reads `created_at`; the API calls it `createdAt`.
    assert order.created_at == "2026-09-10T09:05:36.939Z"


def test_empty_page_is_an_empty_list_not_an_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json(request, {"results": [], "total": 0, "page": 0, "size": 50, "totalPages": 0})

    assert _client(handler).list_orders() == []


# ------------------------------------------------------------------ failures


def test_timeout_is_explicit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow server", request=request)

    with pytest.raises(FourthwallTimeoutError, match="timed out"):
        _client(handler).list_products()


def test_auth_failure_is_explicit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"title": "Unauthorized"}, request=request)

    with pytest.raises(FourthwallAuthError, match="401"):
        _client(handler).list_products()


def test_server_error_is_explicit_never_silent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"title": "Boom"}, request=request)

    with pytest.raises(FourthwallError, match="500"):
        _client(handler).list_products()


def test_transport_failure_is_explicit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("name resolution failed", request=request)

    with pytest.raises(FourthwallError, match="failed"):
        _client(handler).list_products()


def test_non_json_response_is_explicit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>", request=request)

    with pytest.raises(FourthwallError, match="non-JSON"):
        _client(handler).list_products()


def test_missing_credentials_are_loud() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return _json(request, {})

    with pytest.raises(FourthwallConfigError, match="FOURTHWALL_API_USERNAME"):
        _client(handler, password="").list_products()
    with pytest.raises(FourthwallConfigError, match="FOURTHWALL_API_USERNAME"):
        _client(handler, username="").list_products()


def test_missing_base_url_is_loud() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return _json(request, {})

    with pytest.raises(FourthwallConfigError, match="FOURTHWALL_API_BASE_URL"):
        _client(handler, base_url="").list_products()


# ------------------------------------------------------------------- safety


def test_no_write_methods_exist() -> None:
    client = _client(lambda request: _json(request, {}))
    for name in (
        "create_product",
        "update_product",
        "delete_product",
        "archive_product",
        "update_product_availability",
        "publish",
        "write",
        "post",
        "patch",
        "delete",
    ):
        assert not hasattr(client, name)


def test_credentials_never_appear_in_error_messages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"title": "Boom"}, request=request)

    with pytest.raises(FourthwallError) as excinfo:
        _client(handler).list_products()
    message = str(excinfo.value)
    assert PASSWORD not in message
    assert base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode() not in message


def test_since_parameter_is_forwarded() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return _json(request, {"results": [], "total": 0, "page": 0, "size": 50, "totalPages": 0})

    _client(handler).list_orders(limit=3, since="2026-09-01")
    assert seen[0] == {"size": "3", "from": "2026-09-01"}
