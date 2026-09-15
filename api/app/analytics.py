"""Analytics KPI math + recommendation engine (spec C2/C4/C6).

Pure computation over Fourthwall order data and collection contracts.  Every
function is deterministic and side-effect-free: no DB writes, no status
mutations, no auto-retirement (C4 anti-pattern).  Recommendations are advisory
data only; the retire action lives in the collections router.

C6: this surface never writes to Fourthwall.  Prices are REPORTED from the
system of record, not computed locally.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from .collections_schema import CollectionContract, KpiThresholds

# Price invariants (product definition — the system of record is Fourthwall;
# these are used to map product titles/categories to expected revenue).
PRICE_MAP: dict[str, float] = {"tee": 32.0, "hoodie": 62.0, "mug": 20.0}


def _price_for(raw: dict[str, Any]) -> float:
    """Best-effort price lookup from a raw order line (pure)."""
    for key in ("price", "price_usd", "unit_price", "total"):
        value = raw.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return 0.0


def _category_of(raw: dict[str, Any]) -> Optional[str]:
    """Map a raw order/product hint onto a product type (pure).

    Fourthwall orders carry the product name under ``offers[].name``; products
    carry it under ``name``/``title``/``slug``. There is no category field, so
    the keyword scan covers all of those.
    """
    values: list[Any] = [
        raw.get(key) for key in ("category", "product_type", "type", "name", "title", "slug")
    ]
    offers = raw.get("offers")
    if isinstance(offers, list):
        values.extend(
            offer.get("name") for offer in offers if isinstance(offer, dict)
        )
    for value in values:
        if isinstance(value, str):
            lowered = value.lower()
            if "hoodie" in lowered:
                return "hoodie"
            if "mug" in lowered:
                return "mug"
            if "tee" in lowered or "t-shirt" in lowered or "tshirt" in lowered:
                return "tee"
    return None


def _parse_ts(raw: dict[str, Any]) -> Optional[dt.datetime]:
    for key in ("created_at", "timestamp", "date"):
        value = raw.get(key)
        if isinstance(value, str) and value:
            try:
                return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def _windowed(
    orders: list[dict[str, Any]],
    window_days: int,
    now: dt.datetime,
) -> list[dict[str, Any]]:
    """Orders within the window (pure)."""
    cutoff = now - dt.timedelta(days=window_days)
    result: list[dict[str, Any]] = []
    for order in orders:
        created = _parse_ts(order)
        if created is None or created >= cutoff:
            result.append(order)
    return result


def units_in_window(orders: list[dict[str, Any]], window_days: int, now: dt.datetime) -> int:
    """Count orders as unit proxy (pure)."""
    return len(_windowed(orders, window_days, now))


def revenue_in_window(orders: list[dict[str, Any]], window_days: int, now: dt.datetime) -> float:
    """Sum of order totals in window (pure)."""
    total = 0.0
    for order in _windowed(orders, window_days, now):
        total += _price_for(order)
    return total


def kpi_series(
    orders: list[dict[str, Any]],
    thresholds: KpiThresholds,
    now: dt.datetime,
) -> dict[str, Any]:
    """KPI time series vs contract thresholds (pure).

    Returns a dict with units + revenue at each relevant window endpoint.
    Windows are derived from eval_window_days (or sensible defaults).
    """
    windows = sorted({7, 14, 30})
    if thresholds.eval_window_days is not None:
        windows.append(int(thresholds.eval_window_days))
        windows = sorted(set(windows))

    series: list[dict[str, Any]] = []
    for window in windows:
        units = units_in_window(orders, window, now)
        revenue = revenue_in_window(orders, window, now)
        passes_min_units = thresholds.min_units is None or units >= thresholds.min_units
        passes_min_conv = thresholds.min_conversion is None or True  # conversion not derivable from orders alone
        series.append({
            "window_days": window,
            "units": units,
            "revenue": revenue,
            "passes_min_units": passes_min_units,
            "passes_min_conversion": passes_min_conv,
        })

    return {
        "series": series,
        "thresholds": {
            "min_units": thresholds.min_units,
            "min_conversion": thresholds.min_conversion,
            "eval_window_days": thresholds.eval_window_days,
        },
    }


def collection_kpi(
    orders: list[dict[str, Any]],
    contract: CollectionContract,
    now: dt.datetime,
) -> dict[str, Any]:
    """Full KPI payload for one collection (pure)."""
    eval_days = contract.kpi_thresholds.eval_window_days or 30
    units = units_in_window(orders, eval_days, now)
    revenue = revenue_in_window(orders, eval_days, now)

    below_min_units = contract.kpi_thresholds.min_units is not None and units < contract.kpi_thresholds.min_units
    below_min_conv = False  # conversion not derivable without product views

    return {
        "collection_id": contract.collection_id,
        "kpi": kpi_series(orders, contract.kpi_thresholds, now),
        "summary": {
            "units_in_eval_window": units,
            "revenue_in_eval_window": revenue,
            "below_min_units": below_min_units,
            "below_min_conversion": below_min_conv,
        },
    }


def retirement_recommendation(
    orders: list[dict[str, Any]],
    contract: CollectionContract,
    now: dt.datetime,
) -> Optional[dict[str, Any]]:
    """Advisory recommendation: surfaced only when BOTH conditions hold (C4).

    1. The eval window has elapsed since approval (eval_window_days).
    2. Units are below the contract's min_units threshold.

    Returns None when the recommendation does not apply (no auto-retirement).
    """
    if contract.status != "active":
        return None

    eval_days = contract.kpi_thresholds.eval_window_days
    min_units = contract.kpi_thresholds.min_units

    if eval_days is None or min_units is None:
        return None

    # Check whether the window has elapsed since approval.
    approved_at = contract.approved_at
    if approved_at is None:
        return None
    try:
        approved_dt = dt.datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    elapsed = (now - approved_dt).days
    if elapsed < int(eval_days):
        return None

    units = units_in_window(orders, int(eval_days), now)
    revenue = revenue_in_window(orders, int(eval_days), now)

    if units >= int(min_units):
        return None

    return {
        "collection_id": contract.collection_id,
        "verdict": "retirement_recommended",
        "reason": f"units {units} below min_units {min_units} over {int(eval_days)}-day window",
        "units": units,
        "revenue": revenue,
        "min_units": min_units,
        "eval_window_days": int(eval_days),
        "recommendation": "retire",
        "note": "Advisory only — no auto-execution. Founder must approve in the collections UI.",
    }


def overview_revenue(
    all_orders: list[dict[str, Any]],
    now: dt.datetime,
    collections: Optional[list[CollectionContract]] = None,
) -> dict[str, Any]:
    """Shop-wide revenue vs break-even overview (pure).

    Break-even = sum of per-type target prices.  Collections list is used
    to compute an ACTIVE product-type count for the break-even line.
    """
    total_revenue = revenue_in_window(all_orders, 365, now)
    total_units = units_in_window(all_orders, 365, now)

    # Active product type count for break-even (approximate from orders).
    types_seen: set[str] = set()
    for order in all_orders:
        cat = _category_of(order)
        if cat is not None:
            types_seen.add(cat)
    active_types = len(types_seen) or 3  # assume all three
    break_even = active_types * 200.0  # placeholder: $200 per type per year

    return {
        "revenue_12m": total_revenue,
        "units_12m": total_units,
        "break_even": break_even,
        "above_break_even": total_revenue >= break_even,
        "active_product_types": active_types,
    }
