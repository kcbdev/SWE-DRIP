"""Agents API contracts (FR-17, C4).

Offline tests: roster mapping incl. zero-spend, cap edit requires note,
cap > global rejected, routing immutable via API, role matrix, audit payload.
No network, no database.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.agents import (
    AgentInfo,
    GLOBAL_MONTHLY_CAP,
    get_budget_caps,
    set_budget_cap,
)
from api.app.routers.agents import router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _NoopAudit:
    def record(self, **kwargs: Any) -> None:
        pass


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    from api.app.audit import get_audit_writer
    app.dependency_overrides[get_audit_writer] = lambda: _NoopAudit()
    return app


def _client(role: str = ROLE_VIEWER) -> TestClient:
    app = _app()
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-1", "a@b.c", role)
    return TestClient(app, raise_server_exceptions=False)


def _admin_client() -> TestClient:
    return _client(ROLE_ADMIN)


def _viewer_client() -> TestClient:
    return _client(ROLE_VIEWER)


# Fake roster for offline tests (no DB/engine required).
_FAKE_ROSTER = [
    AgentInfo(node="trend_research", role="Trend Research", model="google/gemini-2.0-flash-001", cap_usd=50.0, spend_usd=0.0),
    AgentInfo(node="contract_approval", role="Contract Approval", model="anthropic/claude-sonnet-4-6", cap_usd=50.0, spend_usd=12.5),
    AgentInfo(node="listing_copy", role="Listing Copy", model="anthropic/claude-sonnet-4-6", cap_usd=50.0, spend_usd=0.0),
    AgentInfo(node="design_spec", role="Design Spec", model="anthropic/claude-sonnet-4-6", cap_usd=50.0, spend_usd=0.0),
    AgentInfo(node="art_render", role="Art Render", model="riverflow-v2-pro", cap_usd=50.0, spend_usd=0.0),
    AgentInfo(node="placement", role="Placement", model=None, cap_usd=50.0, spend_usd=0.0),
    AgentInfo(node="aesthetic_qc", role="Aesthetic QC", model="google/gemini-2.0-flash-001", cap_usd=50.0, spend_usd=0.0),
    AgentInfo(node="technical_qc", role="Technical QC", model=None, cap_usd=50.0, spend_usd=0.0),
    AgentInfo(node="fw_create", role="FW Create", model=None, cap_usd=50.0, spend_usd=0.0),
    AgentInfo(node="publish_gate", role="Publish Gate", model=None, cap_usd=50.0, spend_usd=0.0),
    AgentInfo(node="shelf", role="Shelf", model=None, cap_usd=50.0, spend_usd=0.0),
]


def _patch_roster():
    return patch("api.app.routers.agents.get_roster", return_value=_FAKE_ROSTER)


def _patch_detail(node: str = "contract_approval"):
    agent = next((a for a in _FAKE_ROSTER if a.node == node), None)
    return patch("api.app.routers.agents.get_agent_detail", return_value=agent)


# ---------------------------------------------------------------------------
# GET /api/agents — roster
# ---------------------------------------------------------------------------

class TestAgentList:
    def test_returns_all_nodes(self) -> None:
        with _patch_roster():
            resp = _viewer_client().get("/api/agents")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 11

    def test_includes_required_fields(self) -> None:
        with _patch_roster():
            resp = _viewer_client().get("/api/agents")
            agent = resp.json()[0]
            assert "node" in agent
            assert "role" in agent
            assert "model" in agent
            assert "cap_usd" in agent
            assert "spend_usd" in agent
            assert "routing_edit" in agent

    def test_routing_edit_points_to_routing_py(self) -> None:
        with _patch_roster():
            resp = _viewer_client().get("/api/agents")
            for agent in resp.json():
                assert agent["routing_edit"] == "pipeline/routing.py"

    def test_model_none_for_deterministic_nodes(self) -> None:
        with _patch_roster():
            resp = _viewer_client().get("/api/agents")
            placement = next(a for a in resp.json() if a["node"] == "placement")
            assert placement["model"] is None

    def test_zero_spend_by_default(self) -> None:
        with _patch_roster():
            resp = _viewer_client().get("/api/agents")
            trend = next(a for a in resp.json() if a["node"] == "trend_research")
            assert trend["spend_usd"] == 0.0

    def test_viewer_can_read(self) -> None:
        with _patch_roster():
            assert _viewer_client().get("/api/agents").status_code == 200


# ---------------------------------------------------------------------------
# GET /api/agents/{node} — detail
# ---------------------------------------------------------------------------

class TestAgentDetail:
    def test_returns_agent(self) -> None:
        with _patch_detail("contract_approval"):
            resp = _viewer_client().get("/api/agents/contract_approval")
            assert resp.status_code == 200
            assert resp.json()["node"] == "contract_approval"

    def test_unknown_node_404(self) -> None:
        with patch("api.app.routers.agents.get_agent_detail", return_value=None):
            resp = _viewer_client().get("/api/agents/nonexistent")
            assert resp.status_code == 404

    def test_viewer_can_read(self) -> None:
        with _patch_detail():
            assert _viewer_client().get("/api/agents/contract_approval").status_code == 200


# ---------------------------------------------------------------------------
# PATCH /api/agents/{node}/config — budget cap
# ---------------------------------------------------------------------------

class TestAgentConfigPatch:
    def test_update_cap(self) -> None:
        with _patch_detail(), patch("api.app.routers.agents.set_budget_cap") as mock_set:
            mock_set.return_value = {"contract_approval": 75.0}
            resp = _admin_client().patch(
                "/api/agents/contract_approval/config",
                json={"cap_usd": 75.0, "cost_impact_note": "Increasing cap for QA"},
            )
            assert resp.status_code == 200

    def test_requires_cost_impact_note(self) -> None:
        with _patch_detail():
            resp = _admin_client().patch(
                "/api/agents/contract_approval/config",
                json={"cap_usd": 75.0, "cost_impact_note": "   "},
            )
            assert resp.status_code == 400
            assert "cost_impact_note" in resp.json()["detail"]

    def test_rejects_negative_cap(self) -> None:
        with _patch_detail():
            resp = _admin_client().patch(
                "/api/agents/contract_approval/config",
                json={"cap_usd": -10.0, "cost_impact_note": "Negative test"},
            )
            assert resp.status_code == 400
            assert "non-negative" in resp.json()["detail"]

    def test_rejects_cap_above_global(self) -> None:
        with _patch_detail():
            resp = _admin_client().patch(
                "/api/agents/contract_approval/config",
                json={"cap_usd": 200.0, "cost_impact_note": "Over cap test"},
            )
            assert resp.status_code == 400
            assert "global monthly cap" in resp.json()["detail"]

    def test_viewer_cannot_write(self) -> None:
        with _patch_detail():
            resp = _viewer_client().patch(
                "/api/agents/contract_approval/config",
                json={"cap_usd": 75.0, "cost_impact_note": "Viewer test"},
            )
            assert resp.status_code == 403

    def test_unknown_node_404(self) -> None:
        with patch("api.app.routers.agents.get_agent_detail", return_value=None):
            resp = _admin_client().patch(
                "/api/agents/nonexistent/config",
                json={"cap_usd": 75.0, "cost_impact_note": "No such node"},
            )
            assert resp.status_code == 404

    def test_audit_row_written(self) -> None:
        calls: list[dict[str, Any]] = []

        class FakeAudit:
            def record(self, **kwargs: Any) -> None:
                calls.append(kwargs)

        with _patch_detail(), patch("api.app.routers.agents.set_budget_cap"):
            app = _app()
            app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", ROLE_ADMIN)
            from api.app.audit import get_audit_writer
            app.dependency_overrides[get_audit_writer] = lambda: FakeAudit()
            client = TestClient(app, raise_server_exceptions=False)
            client.patch(
                "/api/agents/contract_approval/config",
                json={"cap_usd": 75.0, "cost_impact_note": "Audit test"},
            )
            assert len(calls) == 1
            assert calls[0]["action"] == "agents.budget_cap.update"
            assert calls[0]["entity_id"] == "contract_approval"
            assert calls[0]["after_json"]["cost_impact_note"] == "Audit test"


# ---------------------------------------------------------------------------
# Budget cap store
# ---------------------------------------------------------------------------

class TestBudgetCapStore:
    def test_get_default_caps_empty(self) -> None:
        from api.app.settings_store import reset_cache
        reset_cache()
        caps = get_budget_caps()
        assert caps == {}

    def test_set_and_get_cap(self) -> None:
        from api.app.settings_store import reset_cache
        reset_cache()
        set_budget_cap("contract_approval", 75.0)
        caps = get_budget_caps()
        assert caps["contract_approval"] == 75.0

    def test_global_cap_constant(self) -> None:
        assert GLOBAL_MONTHLY_CAP == 130.0
