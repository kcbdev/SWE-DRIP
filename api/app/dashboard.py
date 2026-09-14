"""Dashboard summary — real data path, no fabricated values (spec C2/C5).

Pure builders (``summarize_spend``, ``summarize_collections``,
``activity_from_audit``) are unit-testable offline. The endpoint assembles them
from pluggable readers; a reader that fails yields explicit ``null`` values plus
a ``sources`` status, so "empty" (zeros/[]) is distinguishable from "broken"
(null + unavailable).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Protocol

from sqlalchemy import text

from .db import get_engine

MONTHLY_CAP_USD = 130.0
SPEND_WARN_RATIO = 0.8
ACTIVITY_LIMIT = 10
PENDING_TOP = 5

COLLECTIONS_DIR = Path(__file__).resolve().parent.parent.parent / "collections"


# ------------------------------------------------------------------ builders


def summarize_spend(rows: list[dict[str, Any]], cap: float = MONTHLY_CAP_USD) -> dict[str, Any]:
    spend = round(sum(float(row.get("cost_usd") or 0) for row in rows), 6)
    pct = round(spend / cap, 4) if cap else 0.0
    return {
        "spend_usd": spend,
        "cap_usd": cap,
        "pct": pct,
        "warning": pct > SPEND_WARN_RATIO,
        "call_count": len(rows),
    }


def _is_at_risk(contract: dict[str, Any]) -> bool:
    thresholds = contract.get("kpi_thresholds") or {}
    current = contract.get("current_kpis") or {}
    for key, floor in thresholds.items():
        if key in current and current[key] < floor:
            return True
    return False


def summarize_collections(contracts: list[dict[str, Any]]) -> dict[str, Any]:
    items = [
        {
            "slug": contract.get("slug"),
            "name": contract.get("name"),
            "at_risk": _is_at_risk(contract),
        }
        for contract in contracts
    ]
    return {
        "count": len(contracts),
        "at_risk": any(item["at_risk"] for item in items),
        "items": items,
    }


def activity_from_audit(entries: list[dict[str, Any]], limit: int = ACTIVITY_LIMIT) -> list[dict[str, Any]]:
    return [
        {
            "action": entry.get("action"),
            "entity_type": entry.get("entity_type"),
            "entity_id": entry.get("entity_id"),
            "actor": entry.get("actor_user_id"),
            "created_at": entry.get("created_at"),
        }
        for entry in entries[:limit]
    ]


# ------------------------------------------------------------------- readers


class CostReader(Protocol):
    def month_rows(self) -> list[dict[str, Any]]: ...


class CollectionsReader(Protocol):
    def contracts(self) -> list[dict[str, Any]]: ...


class PendingApprovalsReader(Protocol):
    def items(self) -> list[dict[str, Any]]: ...


class SqlCostReader:
    """Current-calendar-month rows from ``model_calls`` (owned by this spec)."""

    def month_rows(self) -> list[dict[str, Any]]:
        with get_engine().connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT node, model, tokens_in, tokens_out, cost_usd, created_at "
                    "FROM model_calls "
                    "WHERE created_at >= date_trunc('month', now())"
                )
            ).mappings().all()
        return [dict(row) for row in rows]


class FileCollectionsReader:
    """Contracts via the shared YAML store (PBI-019) — same dict shape as before."""

    def contracts(self) -> list[dict[str, Any]]:
        from .collections_store import get_collections_store

        try:
            return [record["contract"] for record in get_collections_store().list()]
        except Exception:  # noqa: BLE001 - source failure must not 500 the dashboard
            if not COLLECTIONS_DIR.is_dir():
                return []
            raise


class EmptyPendingApprovalsReader:
    """Placeholder until PBI-016 wires the real approvals source (spec C4)."""

    def items(self) -> list[dict[str, Any]]:
        return []


def get_cost_reader() -> CostReader:
    return SqlCostReader()


def get_collections_reader() -> CollectionsReader:
    return FileCollectionsReader()


def get_pending_approvals_reader() -> PendingApprovalsReader:
    return EmptyPendingApprovalsReader()


# ---------------------------------------------------------------- assembly


def _safe(fn: Any) -> tuple[Any, str]:
    try:
        return fn(), "ok"
    except Exception:  # noqa: BLE001 - source failure must not 500 the dashboard
        return None, "unavailable"


def build_summary(
    *,
    spend_rows: Optional[list[dict[str, Any]]],
    contracts: Optional[list[dict[str, Any]]],
    audit_entries: Optional[list[dict[str, Any]]],
    pending: Optional[list[dict[str, Any]]],
) -> dict[str, Any]:
    spend: Any = None if spend_rows is None else summarize_spend(spend_rows)
    collections: Any = None if contracts is None else summarize_collections(contracts)
    activity: Any = None if audit_entries is None else activity_from_audit(audit_entries)
    pending_items = pending or []
    return {
        "pending_approvals": {
            "count": None if pending is None else len(pending_items),
            "items": pending_items[:PENDING_TOP],
        },
        "spend": spend,
        "collections": collections,
        "activity": activity,
        "sources": {
            "spend": "ok" if spend_rows is not None else "unavailable",
            "collections": "ok" if contracts is not None else "unavailable",
            "activity": "ok" if audit_entries is not None else "unavailable",
            "pending_approvals": "ok" if pending is not None else "unavailable",
        },
    }
