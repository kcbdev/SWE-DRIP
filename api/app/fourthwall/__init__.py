"""Fourthwall integration package — reads only (spec C3: no Control Panel writes)."""

from .client import (
    AnalyticsReport,
    FourthwallAuthError,
    FourthwallConfigError,
    FourthwallError,
    FourthwallReadClient,
    FourthwallTimeoutError,
    Order,
    Product,
    get_fourthwall_client,
)

__all__ = [
    "AnalyticsReport",
    "FourthwallAuthError",
    "FourthwallConfigError",
    "FourthwallError",
    "FourthwallReadClient",
    "FourthwallTimeoutError",
    "Order",
    "Product",
    "get_fourthwall_client",
]
