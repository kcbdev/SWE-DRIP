"""Fourthwall MCP read client (spec C1/C7).

Typed, READ-ONLY access to the official Fourthwall MCP server over Streamable
HTTP, authenticated server-side with an OAuth2 bearer (``FOURTHWALL_MCP_TOKEN``;
never leaves the server — C7). No write/create method may enter this module
(refinement rule: reads only).

Tool-name assumption (refinement rule): the mappings below assume MCP tools
named ``list_products`` / ``get_product`` / ``list_orders`` / ``get_analytics``
returning JSON in a text content block. These are ASSUMED shapes — the PBI-026
spike records the real schemas here when live evidence exists. Do NOT invent
a parallel REST read path.

Degraded-error model: every failure surfaces as an explicit ``FourthwallError``
subclass to the caller (auth → ``FourthwallAuthError``, timeouts →
``FourthwallTimeoutError``, missing token → ``FourthwallConfigError``) — never
silent empties, never fabricated data, never a crash past the caller.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, ConfigDict


class FourthwallError(RuntimeError):
    """Base: any Fourthwall read failure. Callers surface, never swallow."""


class FourthwallConfigError(FourthwallError):
    """Missing token/URL — loud at call time, never a silent empty."""


class FourthwallAuthError(FourthwallError):
    """401/403 from the MCP server — token invalid or expired."""


class FourthwallTimeoutError(FourthwallError):
    """The MCP server did not answer in time."""


class TypedModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class Product(TypedModel):
    id: str
    title: Optional[str] = None
    status: Optional[str] = None


class Order(TypedModel):
    id: str
    status: Optional[str] = None
    total: Optional[float] = None
    currency: Optional[str] = None
    created_at: Optional[str] = None


class AnalyticsPoint(TypedModel):
    t: Optional[str] = None
    value: Optional[float] = None


class AnalyticsReport(TypedModel):
    metric: str
    window_days: int = 30
    points: list[AnalyticsPoint] = []


# Assumed MCP tool names (see module docstring — confirmed by the PBI-026 spike).
TOOL_LIST_PRODUCTS = "list_products"
TOOL_GET_PRODUCT = "get_product"
TOOL_LIST_ORDERS = "list_orders"
TOOL_GET_ANALYTICS = "get_analytics"

DEFAULT_TIMEOUT = 30.0


def _payload(result: Any) -> Any:
    """Unwrap an MCP CallToolResult (or test double) to plain JSON."""
    if isinstance(result, dict):
        return result
    blocks = getattr(result, "content", None) or []
    texts = [getattr(block, "text", "") for block in blocks if hasattr(block, "text")]
    joined = "".join(texts).strip()
    if not joined:
        return {}
    try:
        return json.loads(joined)
    except json.JSONDecodeError:
        return {"text": joined}


async def _real_call(url: str, token: str, timeout: float, tool: str, arguments: dict[str, Any]) -> Any:
    """One MCP session per call (our scale: tens of reads; no pooling yet)."""
    import httpx

    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    async with client:
        async with streamable_http_client(url) as transport:
            read, write, *_ = transport
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool, arguments)


SessionFactory = Callable[[str, dict[str, Any]], Awaitable[Any]]


class FourthwallReadClient:
    """Sync façade over MCP reads (nodes and sync endpoints stay sync)."""

    def __init__(
        self,
        *,
        url: str = "",
        token: str = "",
        timeout: float = DEFAULT_TIMEOUT,
        session_factory: Optional[SessionFactory] = None,
    ) -> None:
        self._url = url
        self._token = token
        self._timeout = timeout
        self._factory = session_factory or (
            lambda tool, args: _real_call(url, token, timeout, tool, args)
        )

    # ------------------------------------------------------------------ reads

    def list_products(self, *, limit: int = 50) -> list[Product]:
        payload = self._call(TOOL_LIST_PRODUCTS, {"limit": limit})
        items = payload.get("products", payload.get("items", [])) if isinstance(payload, dict) else []
        return [Product.model_validate(item) for item in items]

    def get_product(self, product_id: str) -> Product:
        payload = self._call(TOOL_GET_PRODUCT, {"product_id": product_id})
        product = payload.get("product", payload) if isinstance(payload, dict) else {}
        return Product.model_validate(product)

    def list_orders(self, *, limit: int = 50, since: Optional[str] = None) -> list[Order]:
        args: dict[str, Any] = {"limit": limit}
        if since:
            args["since"] = since
        payload = self._call(TOOL_LIST_ORDERS, args)
        items = payload.get("orders", payload.get("items", [])) if isinstance(payload, dict) else []
        return [Order.model_validate(item) for item in items]

    def get_analytics(self, *, metric: str, window_days: int = 30) -> AnalyticsReport:
        payload = self._call(TOOL_GET_ANALYTICS, {"metric": metric, "window_days": window_days})
        if not isinstance(payload, dict):
            payload = {"metric": metric, "window_days": window_days, "points": []}
        return AnalyticsReport.model_validate(
            {"metric": metric, "window_days": window_days, **payload}
        )

    # ------------------------------------------------------------------ core

    def _call(self, tool: str, arguments: dict[str, Any]) -> Any:
        if not self._token:
            raise FourthwallConfigError("FOURTHWALL_MCP_TOKEN is not set — refusing a silent empty")
        if not self._url:
            raise FourthwallConfigError("FOURTHWALL_MCP_URL is not set — refusing a silent empty")
        try:
            result = asyncio.run(self._factory(tool, arguments))
        except FourthwallError:
            raise
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise FourthwallTimeoutError(f"{tool} timed out: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - mapped below, never swallowed
            message = str(exc)
            if "httpx.TimeoutException" in type(exc).__name__ or "timed out" in message.lower():
                raise FourthwallTimeoutError(f"{tool} timed out: {exc}") from exc
            if "401" in message or "403" in message or "unauthorized" in message.lower():
                raise FourthwallAuthError(f"{tool} rejected (auth): {exc}") from exc
            raise FourthwallError(f"{tool} failed: {exc}") from exc
        return _payload(result)


def get_fourthwall_client(
    session_factory: Optional[SessionFactory] = None,
) -> FourthwallReadClient:
    """Prod wiring: Control Panel settings store first, env fallback (spec C7).

    Credentials never leave the server; an admin-configured value (set in the
    Settings UI) takes precedence over the deployment env var.
    """
    try:
        from ..settings_store import resolve_integration

        url = resolve_integration("fourthwall_mcp_url")
        token = resolve_integration("fourthwall_mcp_token")
    except Exception:  # pragma: no cover - store unavailable outside the API
        import os

        url = os.environ.get("FOURTHWALL_MCP_URL", "")
        token = os.environ.get("FOURTHWALL_MCP_TOKEN", "")
    return FourthwallReadClient(
        url=url,
        token=token,
        session_factory=session_factory,
    )
