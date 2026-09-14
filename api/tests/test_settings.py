"""Settings API contracts (spec C1/C2/C3/C5/C6).

Offline tests: HITL toggle round-trip + audit, brand edit audit,
integrations presence-only shape, role matrix, pipeline flag resolution.
No network, no database.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor, get_current_actor
from api.app.settings_store import (
    _DEFAULT_BRAND,
    _DEFAULT_HITL,
    get_brand,
    get_hitl_flags,
    get_integrations,
    reset_cache,
    set_brand,
    set_hitl_flags,
)
from api.app.routers.settings import router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _NoopAudit:
    """Audit writer that discards writes — for tests with no DB."""

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


def _operator_client() -> TestClient:
    return _client(ROLE_OPERATOR)


# ---------------------------------------------------------------------------
# HITL flags
# ---------------------------------------------------------------------------

class TestHitlGet:
    def test_returns_all_nodes(self) -> None:
        reset_cache()
        resp = _viewer_client().get("/api/settings/hitl")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == set(_DEFAULT_HITL.keys())

    def test_default_values_match(self) -> None:
        reset_cache()
        resp = _viewer_client().get("/api/settings/hitl")
        assert resp.json()["contract_approval"] is True
        assert resp.json()["aesthetic_qc"] is True
        assert resp.json()["trend_research"] is False

    def test_viewer_can_read(self) -> None:
        reset_cache()
        assert _viewer_client().get("/api/settings/hitl").status_code == 200

    def test_operator_can_read(self) -> None:
        reset_cache()
        assert _operator_client().get("/api/settings/hitl").status_code == 200


class TestHitlPatch:
    def test_toggle_with_confirmation(self) -> None:
        reset_cache()
        resp = _admin_client().patch(
            "/api/settings/hitl",
            json={"node": "publish_gate", "enabled": False, "confirm": True},
        )
        assert resp.status_code == 200
        assert resp.json()["publish_gate"] is False

    def test_toggle_round_trip(self) -> None:
        reset_cache()
        # Off
        _admin_client().patch(
            "/api/settings/hitl",
            json={"node": "publish_gate", "enabled": False, "confirm": True},
        )
        # On
        resp = _admin_client().patch(
            "/api/settings/hitl",
            json={"node": "publish_gate", "enabled": True, "confirm": True},
        )
        assert resp.json()["publish_gate"] is True

    def test_requires_confirmation(self) -> None:
        reset_cache()
        resp = _admin_client().patch(
            "/api/settings/hitl",
            json={"node": "publish_gate", "enabled": False, "confirm": False},
        )
        assert resp.status_code == 400
        assert "Confirmation required" in resp.json()["detail"]

    def test_unknown_node_404(self) -> None:
        reset_cache()
        resp = _admin_client().patch(
            "/api/settings/hitl",
            json={"node": "nonexistent", "enabled": True, "confirm": True},
        )
        assert resp.status_code == 404

    def test_viewer_cannot_write(self) -> None:
        reset_cache()
        resp = _viewer_client().patch(
            "/api/settings/hitl",
            json={"node": "publish_gate", "enabled": False, "confirm": True},
        )
        assert resp.status_code == 403

    def test_operator_cannot_write(self) -> None:
        reset_cache()
        resp = _operator_client().patch(
            "/api/settings/hitl",
            json={"node": "publish_gate", "enabled": False, "confirm": True},
        )
        assert resp.status_code == 403

    def test_audit_row_written(self) -> None:
        """Verify the audit writer is called with correct params."""
        reset_cache()
        calls: list[dict[str, Any]] = []

        class FakeAudit:
            def record(self, **kwargs: Any) -> None:
                calls.append(kwargs)

        app = _app()
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", ROLE_ADMIN)
        # Inject fake audit writer
        from api.app.audit import AuditWriter, get_audit_writer
        app.dependency_overrides[get_audit_writer] = lambda: FakeAudit()
        client = TestClient(app, raise_server_exceptions=False)
        client.patch(
            "/api/settings/hitl",
            json={"node": "publish_gate", "enabled": False, "confirm": True},
        )
        assert len(calls) == 1
        assert calls[0]["action"] == "settings.hitl.toggle"
        assert calls[0]["entity_id"] == "publish_gate"
        assert calls[0]["before_json"]["enabled"] is True
        assert calls[0]["after_json"]["enabled"] is False


# ---------------------------------------------------------------------------
# Brand-lock constants
# ---------------------------------------------------------------------------

class TestBrandGet:
    def test_returns_brand(self) -> None:
        reset_cache()
        resp = _viewer_client().get("/api/settings/brand")
        assert resp.status_code == 200
        data = resp.json()
        assert "palette" in data
        assert "typeface" in data
        assert "forbidden" in data

    def test_default_palette(self) -> None:
        reset_cache()
        resp = _viewer_client().get("/api/settings/brand")
        assert resp.json()["palette"]["void_black"] == "#0D0D0D"
        assert resp.json()["palette"]["terminal_green"] == "#00FF41"

    def test_default_typeface(self) -> None:
        reset_cache()
        resp = _viewer_client().get("/api/settings/brand")
        assert resp.json()["typeface"] == "JetBrains Mono"

    def test_default_forbidden(self) -> None:
        reset_cache()
        resp = _viewer_client().get("/api/settings/brand")
        assert "gradients" in resp.json()["forbidden"]
        assert "shadows" in resp.json()["forbidden"]


class TestBrandPatch:
    def test_update_palette(self) -> None:
        reset_cache()
        resp = _admin_client().patch(
            "/api/settings/brand",
            json={"palette": {"void_black": "#000000"}, "confirm": True},
        )
        assert resp.status_code == 200
        assert resp.json()["palette"]["void_black"] == "#000000"
        # Other palette keys preserved
        assert resp.json()["palette"]["terminal_green"] == "#00FF41"

    def test_update_typeface(self) -> None:
        reset_cache()
        resp = _admin_client().patch(
            "/api/settings/brand",
            json={"typeface": "Fira Code", "confirm": True},
        )
        assert resp.status_code == 200
        assert resp.json()["typeface"] == "Fira Code"

    def test_requires_confirmation(self) -> None:
        reset_cache()
        resp = _admin_client().patch(
            "/api/settings/brand",
            json={"typeface": "Fira Code", "confirm": False},
        )
        assert resp.status_code == 400

    def test_viewer_cannot_write(self) -> None:
        reset_cache()
        resp = _viewer_client().patch(
            "/api/settings/brand",
            json={"typeface": "Fira Code", "confirm": True},
        )
        assert resp.status_code == 403

    def test_audit_row_written(self) -> None:
        reset_cache()
        calls: list[dict[str, Any]] = []

        class FakeAudit:
            def record(self, **kwargs: Any) -> None:
                calls.append(kwargs)

        app = _app()
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", ROLE_ADMIN)
        from api.app.audit import AuditWriter, get_audit_writer
        app.dependency_overrides[get_audit_writer] = lambda: FakeAudit()
        client = TestClient(app, raise_server_exceptions=False)
        client.patch(
            "/api/settings/brand",
            json={"typeface": "Fira Code", "confirm": True},
        )
        assert len(calls) == 1
        assert calls[0]["action"] == "settings.brand.update"
        assert calls[0]["entity_id"] == "brand"


# ---------------------------------------------------------------------------
# Integrations status
# ---------------------------------------------------------------------------

class TestIntegrations:
    def test_returns_shape(self) -> None:
        reset_cache()
        resp = _viewer_client().get("/api/settings/integrations")
        assert resp.status_code == 200
        data = resp.json()
        assert "fourthwall_mcp" in data
        assert "openrouter" in data
        assert isinstance(data["fourthwall_mcp"], bool)
        assert isinstance(data["openrouter"], bool)

    def test_no_secrets_leaked(self) -> None:
        """Ensure no secret values are exposed."""
        reset_cache()
        resp = _viewer_client().get("/api/settings/integrations")
        data = resp.json()
        for key, val in data.items():
            # Values must be booleans, never strings
            assert isinstance(val, bool), f"{key} should be bool, got {type(val)}"

    def test_viewer_can_read(self) -> None:
        reset_cache()
        assert _viewer_client().get("/api/settings/integrations").status_code == 200

    def test_unconfigured_by_default(self) -> None:
        reset_cache()
        with patch("api.app.settings_store.get_integrations", return_value={"fourthwall_mcp": False, "openrouter": False}):
            resp = _viewer_client().get("/api/settings/integrations")
            assert resp.json()["fourthwall_mcp"] is False
            assert resp.json()["openrouter"] is False


# ---------------------------------------------------------------------------
# Pipeline settings wiring
# ---------------------------------------------------------------------------

class TestPipelineSettings:
    def test_resolve_hitl_flags_uses_store(self) -> None:
        """Pipeline settings resolver reads from the store."""
        reset_cache()
        from pipeline.settings import resolve_hitl_flags
        flags = resolve_hitl_flags()
        assert isinstance(flags, dict)
        assert "publish_gate" in flags
        assert flags["publish_gate"] is True

    def test_is_hitl_enabled_default(self) -> None:
        reset_cache()
        from pipeline.settings import is_hitl_enabled
        assert is_hitl_enabled("publish_gate") is True
        assert is_hitl_enabled("trend_research") is False

    def test_is_hitl_enabled_unknown_defaults_false(self) -> None:
        reset_cache()
        from pipeline.settings import is_hitl_enabled
        assert is_hitl_enabled("nonexistent_node") is False

    def test_store_change_reflected(self) -> None:
        reset_cache()
        from pipeline.settings import is_hitl_enabled
        set_hitl_flags({"publish_gate": False})
        assert is_hitl_enabled("publish_gate") is False
        # Restore
        set_hitl_flags({"publish_gate": True})
