"""Dashboard summary contract tests (offline)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.audit import AuditFilters, get_audit_reader
from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.dashboard import (
    MONTHLY_CAP_USD,
    activity_from_audit,
    build_summary,
    get_collections_reader,
    get_cost_reader,
    get_pending_approvals_reader,
    summarize_collections,
    summarize_spend,
)
from api.app.routers import dashboard as dashboard_router


# ------------------------------------------------------------------- spend


def test_spend_rollup_and_no_warning_below_threshold() -> None:
    rows = [{"cost_usd": 30.0}, {"cost_usd": 20.5}]
    result = summarize_spend(rows)
    assert result["spend_usd"] == 50.5
    assert result["cap_usd"] == MONTHLY_CAP_USD
    assert result["warning"] is False


def test_spend_warning_above_80_percent() -> None:
    result = summarize_spend([{"cost_usd": 104.01}])
    assert result["warning"] is True
    assert result["pct"] > 0.8


def test_spend_exactly_at_80_percent_is_not_a_warning() -> None:
    result = summarize_spend([{"cost_usd": 104.0}])
    assert result["warning"] is False


def test_spend_ignores_null_cost() -> None:
    assert summarize_spend([{"cost_usd": None}, {"cost_usd": 5}])["spend_usd"] == 5.0


# ------------------------------------------------------------- collections


def test_collections_zero() -> None:
    assert summarize_collections([]) == {"count": 0, "at_risk": False, "items": []}


def test_collections_one_healthy() -> None:
    result = summarize_collections([{"slug": "gym", "name": "Gym"}])
    assert result["count"] == 1
    assert result["at_risk"] is False


def test_collections_at_risk_when_kpi_below_threshold() -> None:
    contract = {
        "slug": "gym",
        "kpi_thresholds": {"conversion": 0.02},
        "current_kpis": {"conversion": 0.01},
    }
    assert summarize_collections([contract])["at_risk"] is True


# ---------------------------------------------------------------- activity


def test_activity_maps_and_limits() -> None:
    entries = [
        {
            "actor_user_id": "u-1",
            "action": "auth.login",
            "entity_type": "session",
            "entity_id": "s-1",
            "created_at": "2026-09-13T10:00:00Z",
        },
        {"actor_user_id": "u-2", "action": "role.change", "entity_type": "user", "entity_id": None, "created_at": "x"},
    ]
    mapped = activity_from_audit(entries, limit=1)
    assert len(mapped) == 1
    assert mapped[0]["actor"] == "u-1"
    assert mapped[0]["action"] == "auth.login"


# --------------------------------------------------------------- assembly


def test_empty_sources_are_zeros_not_nulls() -> None:
    summary = build_summary(spend_rows=[], contracts=[], audit_entries=[], pending=[])
    assert summary["spend"]["spend_usd"] == 0.0
    assert summary["collections"]["count"] == 0
    assert summary["activity"] == []
    assert summary["pending_approvals"]["count"] == 0
    assert all(status == "ok" for status in summary["sources"].values())


def test_broken_sources_are_explicit_nulls() -> None:
    summary = build_summary(spend_rows=None, contracts=None, audit_entries=None, pending=None)
    assert summary["spend"] is None
    assert summary["collections"] is None
    assert summary["activity"] is None
    assert summary["pending_approvals"]["count"] is None
    assert summary["sources"]["spend"] == "unavailable"


# ---------------------------------------------------------------- endpoint


class FakeAudit:
    def list_entries(self, filters: AuditFilters) -> list[dict[str, Any]]:
        return []


class FakeCosts:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def month_rows(self) -> list[dict[str, Any]]:
        return self.rows


class BoomCosts:
    def month_rows(self) -> list[dict[str, Any]]:
        raise RuntimeError("db down")


class FakeCollections:
    def contracts(self) -> list[dict[str, Any]]:
        return [{"slug": "gym", "name": "Gym"}]


class FakePending:
    def items(self) -> list[dict[str, Any]]:
        return []


def _client(role: str = ROLE_VIEWER, costs: Any = None) -> TestClient:
    app = FastAPI()
    app.include_router(dashboard_router.router)
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-1", "a@b.c", role)
    app.dependency_overrides[get_audit_reader] = lambda: FakeAudit()
    app.dependency_overrides[get_cost_reader] = lambda: costs or FakeCosts([{"cost_usd": 10.0}])
    app.dependency_overrides[get_collections_reader] = lambda: FakeCollections()
    app.dependency_overrides[get_pending_approvals_reader] = lambda: FakePending()
    return TestClient(app)


def test_endpoint_summary_shape() -> None:
    response = _client().get("/api/dashboard/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["spend"]["spend_usd"] == 10.0
    assert body["collections"]["count"] == 1
    assert body["pending_approvals"]["count"] == 0


def test_endpoint_degrades_broken_source() -> None:
    body = _client(costs=BoomCosts()).get("/api/dashboard/summary").json()
    assert body["spend"] is None
    assert body["sources"]["spend"] == "unavailable"
    assert body["collections"]["count"] == 1


def test_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(dashboard_router.router)
    assert TestClient(app).get("/api/dashboard/summary").status_code == 401


def test_admin_also_allowed() -> None:
    assert _client(role=ROLE_ADMIN).get("/api/dashboard/summary").status_code == 200
