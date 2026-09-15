"""Fourthwall Platform Open API read client (spec C1/C7).

Typed, READ-ONLY access to the Fourthwall Platform Open API over HTTPS,
authenticated server-side with shop-level HTTP Basic credentials
(``FOURTHWALL_API_USERNAME`` / ``FOURTHWALL_API_PASSWORD``; never leaves the
server — C7). No write/create method may enter this module (refinement rule:
reads only).

Endpoint + auth are taken from the official docs (verified live 2026-09-15):

- Base URL:  ``https://api.fourthwall.com``
- Products:  ``GET /open-api/v1.0/products`` (paged ``{results,total,page,size,totalPages}``)
- Product:   ``GET /open-api/v1.0/products/{productId}``
- Orders:    ``GET /open-api/v1.0/order`` (paged)
- Auth:      ``Authorization: Basic base64(username:password)``

Why not the MCP server? ``https://mcp.fourthwall.com`` is OAuth 2.0 only
(authorization_code + PKCE, dynamic client registration) — it cannot accept a
static configured credential, and every call this codebase makes is a plain
product/order read that the Open API covers. See ADR-005.

Field normalization lives HERE, at the single integration boundary: the API's
nested shapes (``state.type``, ``variants[].unitPrice.value``,
``amounts.total.value``, ``createdAt``) are flattened onto the typed models so
routers stay dumb and no consumer re-implements the mapping.

Degraded-error model: every failure surfaces as an explicit ``FourthwallError``
subclass to the caller (auth → ``FourthwallAuthError``, timeouts →
``FourthwallTimeoutError``, missing credentials → ``FourthwallConfigError``)
— never silent empties, never fabricated data, never a crash past the caller.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

import httpx
from pydantic import BaseModel, ConfigDict, model_validator

OPEN_API_BASE_URL = "https://api.fourthwall.com"
PRODUCTS_PATH = "/open-api/v1.0/products"
ORDERS_PATH = "/open-api/v1.0/order"

DEFAULT_TIMEOUT = 30.0
DEFAULT_PAGE_SIZE = 50


class FourthwallError(RuntimeError):
    """Base: any Fourthwall read failure. Callers surface, never swallow."""


class FourthwallConfigError(FourthwallError):
    """Missing credentials/base URL — loud at call time, never a silent empty."""


class FourthwallAuthError(FourthwallError):
    """401/403 from the API — credentials invalid or lacking permission."""


class FourthwallTimeoutError(FourthwallError):
    """The API did not answer in time."""


class TypedModel(BaseModel):
    model_config = ConfigDict(extra="allow")


def _money_value(node: Any) -> Optional[float]:
    """Extract a float from a Fourthwall ``Money`` node (``{value, currency}``)."""
    if isinstance(node, dict):
        value = node.get("value")
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        return float(node)
    return None


def _money_currency(node: Any) -> Optional[str]:
    if isinstance(node, dict):
        currency = node.get("currency")
        if isinstance(currency, str):
            return currency
    return None


class Product(TypedModel):
    """A Fourthwall product (offer), flattened for the catalog mirror."""

    id: str
    name: Optional[str] = None
    slug: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    variants: list[dict[str, Any]] = []

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        # status <- state.type (AVAILABLE | SOLD_OUT)
        state = data.get("state")
        if isinstance(state, dict) and isinstance(state.get("type"), str):
            data.setdefault("status", state["type"])
        # price/currency <- first variant's unitPrice Money node
        variants = data.get("variants")
        if isinstance(variants, list) and variants:
            first = variants[0] if isinstance(variants[0], dict) else {}
            unit_price = first.get("unitPrice")
            if data.get("price") is None:
                data["price"] = _money_value(unit_price)
            if data.get("currency") is None:
                data["currency"] = _money_currency(unit_price)
        return data


class Order(TypedModel):
    """A Fourthwall order, flattened for KPI math."""

    id: str
    status: Optional[str] = None
    total: Optional[float] = None
    currency: Optional[str] = None
    created_at: Optional[str] = None
    email: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        amounts = data.get("amounts")
        total = amounts.get("total") if isinstance(amounts, dict) else None
        if data.get("total") is None:
            data["total"] = _money_value(total)
        if data.get("currency") is None:
            data["currency"] = _money_currency(total)
        # The KPI window math reads `created_at`; the API calls it `createdAt`.
        if data.get("created_at") is None and isinstance(data.get("createdAt"), str):
            data["created_at"] = data["createdAt"]
        return data


class FourthwallReadClient:
    """Sync facade over the Fourthwall Platform Open API (reads only)."""

    def __init__(
        self,
        *,
        base_url: str = "",
        username: str = "",
        password: str = "",
        timeout: float = DEFAULT_TIMEOUT,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._username = username
        self._password = password
        self._timeout = timeout
        self._transport = transport

    # ------------------------------------------------------------------ reads

    def list_products(self, *, limit: int = DEFAULT_PAGE_SIZE) -> list[Product]:
        payload = self._get(PRODUCTS_PATH, {"size": limit})
        return [Product.model_validate(item) for item in _results(payload)]

    def get_product(self, product_id: str) -> Product:
        payload = self._get(f"{PRODUCTS_PATH}/{product_id}", {})
        node = payload if isinstance(payload, dict) else {}
        return Product.model_validate(node)

    def list_orders(self, *, limit: int = DEFAULT_PAGE_SIZE, since: Optional[str] = None) -> list[Order]:
        params: dict[str, Any] = {"size": limit}
        if since:
            params["from"] = since
        payload = self._get(ORDERS_PATH, params)
        return [Order.model_validate(item) for item in _results(payload)]

    # ------------------------------------------------------------------ core

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        if not self._username or not self._password:
            raise FourthwallConfigError(
                "FOURTHWALL_API_USERNAME/FOURTHWALL_API_PASSWORD are not both set "
                "— refusing a silent empty"
            )
        if not self._base_url:
            raise FourthwallConfigError(
                "FOURTHWALL_API_BASE_URL is not set — refusing a silent empty"
            )
        try:
            with httpx.Client(
                base_url=self._base_url,
                transport=self._transport,
                timeout=self._timeout,
                headers={"Authorization": self._basic_auth_header()},
            ) as client:
                response = client.get(path, params=dict(params))
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise FourthwallTimeoutError(f"GET {path} timed out: {exc}") from exc
        except httpx.HTTPError as exc:  # connection/transport issues
            raise FourthwallError(f"GET {path} failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise FourthwallAuthError(
                f"GET {path} rejected (auth): HTTP {response.status_code}"
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise FourthwallError(
                f"GET {path} failed: HTTP {response.status_code}"
            ) from exc
        try:
            return response.json()
        except ValueError as exc:
            raise FourthwallError(f"GET {path} failed: non-JSON response") from exc

    def _basic_auth_header(self) -> str:
        raw = f"{self._username}:{self._password}".encode("utf-8")
        return f"Basic {base64.b64encode(raw).decode('ascii')}"


def _results(payload: Any) -> list[dict[str, Any]]:
    """Unwrap the paged envelope (``{results:[...]}``) or a bare list."""
    if isinstance(payload, dict):
        items = payload.get("results")
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def get_fourthwall_client() -> FourthwallReadClient:
    """Prod wiring: Control Panel settings store first, env fallback (spec C7).

    Credentials never leave the server; an admin-configured value (set in the
    Settings UI) takes precedence over the deployment env var.

    Takes no arguments on purpose: this function is a FastAPI dependency, and
    FastAPI would try to bind any parameter as a request field. Tests inject a
    client by overriding the dependency, or build ``FourthwallReadClient``
    directly with a mock ``transport``.
    """
    try:
        from ..settings_store import resolve_integration

        base_url = resolve_integration("fourthwall_api_base_url", OPEN_API_BASE_URL)
        username = resolve_integration("fourthwall_api_username")
        password = resolve_integration("fourthwall_api_password")
    except Exception:  # pragma: no cover - store unavailable outside the API
        import os

        base_url = os.environ.get("FOURTHWALL_API_BASE_URL", OPEN_API_BASE_URL)
        username = os.environ.get("FOURTHWALL_API_USERNAME", "")
        password = os.environ.get("FOURTHWALL_API_PASSWORD", "")
    return FourthwallReadClient(
        base_url=base_url,
        username=username,
        password=password,
    )
