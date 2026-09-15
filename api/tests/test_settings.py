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
        assert calls[0]["before"]["enabled"] is True
        assert calls[0]["after"]["enabled"] is False


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
        """Only presence booleans and non-secret endpoints may be exposed."""
        reset_cache()
        resp = _viewer_client().get("/api/settings/integrations")
        data = resp.json()
        assert set(data) == {
            "fourthwall_mcp",
            "openrouter",
            "fourthwall_mcp_url",
            "openrouter_base_url",
        }
        for key in ("fourthwall_mcp_token", "openrouter_api_key"):
            assert key not in data

    def test_viewer_can_read(self) -> None:
        reset_cache()
        assert _viewer_client().get("/api/settings/integrations").status_code == 200

    def test_unconfigured_by_default(self) -> None:
        reset_cache()
        with patch("api.app.settings_store.get_integrations", return_value={"fourthwall_mcp": False, "openrouter": False}):
            resp = _viewer_client().get("/api/settings/integrations")
            assert resp.json()["fourthwall_mcp"] is False
            assert resp.json()["openrouter"] is False


class TestIntegrationsCredentials:
    """Admin-configurable credentials: store round-trip, role gate, audit."""

    def test_admin_can_set_and_read_back_presence(self) -> None:
        reset_cache()
        resp = _admin_client().patch(
            "/api/settings/integrations",
            json={
                "fourthwall_mcp_url": "https://mcp.example/fourthwall",
                "fourthwall_mcp_token": "fw-secret-token",
                "openrouter_api_key": "openrouter-test-key",
                "confirm": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fourthwall_mcp"] is True
        assert data["openrouter"] is True
        assert data["fourthwall_mcp_url"] == "https://mcp.example/fourthwall"
        # Secrets are never echoed back, even in the write response.
        assert "fourthwall_mcp_token" not in data
        assert "openrouter_api_key" not in data
        assert "fw-secret-token" not in resp.text
        assert "openrouter-test-key" not in resp.text

    def test_stored_value_beats_env_and_clear_reverts(self) -> None:
        reset_cache()
        from api.app.settings_store import resolve_integration

        with patch("api.app.config.settings.openrouter_api_key", "env-key"):
            assert resolve_integration("openrouter_api_key") == "env-key"
            _admin_client().patch(
                "/api/settings/integrations",
                json={"openrouter_api_key": "ui-key", "confirm": True},
            )
            assert resolve_integration("openrouter_api_key") == "ui-key"
            _admin_client().patch(
                "/api/settings/integrations",
                json={"openrouter_api_key": "", "confirm": True},
            )
            assert resolve_integration("openrouter_api_key") == "env-key"

    def test_confirm_required(self) -> None:
        reset_cache()
        resp = _admin_client().patch(
            "/api/settings/integrations",
            json={"openrouter_api_key": "k", "confirm": False},
        )
        assert resp.status_code == 400

    def test_empty_patch_rejected(self) -> None:
        reset_cache()
        resp = _admin_client().patch(
            "/api/settings/integrations",
            json={"confirm": True},
        )
        assert resp.status_code == 400

    def test_operator_cannot_write(self) -> None:
        reset_cache()
        resp = _client(ROLE_OPERATOR).patch(
            "/api/settings/integrations",
            json={"openrouter_api_key": "k", "confirm": True},
        )
        assert resp.status_code == 403

    def test_update_is_audited_without_secrets(self) -> None:
        reset_cache()
        app = _app()
        calls: list[dict] = []

        class _RecordingAudit:
            def record(self, **kwargs: Any) -> None:
                calls.append(kwargs)

        from api.app.audit import get_audit_writer
        from api.app.auth import get_current_actor as live_actor

        app.dependency_overrides[get_audit_writer] = lambda: _RecordingAudit()
        app.dependency_overrides[live_actor] = lambda: Actor("u-9", "a@b.c", ROLE_ADMIN)
        client = TestClient(app, raise_server_exceptions=False)
        client.patch(
            "/api/settings/integrations",
            json={"fourthwall_mcp_token": "top-secret", "confirm": True},
        )
        assert len(calls) == 1
        assert calls[0]["action"] == "settings.integrations.update"
        assert calls[0]["entity_id"] == "integrations"
        assert "top-secret" not in str(calls[0])

    def test_test_endpoint_reports_missing_config(self) -> None:
        reset_cache()
        resp = _admin_client().post("/api/settings/integrations/test")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
        assert "not both configured" in resp.json()["error"]

    def test_test_endpoint_reports_probe_failure(self) -> None:
        reset_cache()
        from api.app.fourthwall.client import FourthwallError

        _admin_client().patch(
            "/api/settings/integrations",
            json={"fourthwall_mcp_url": "https://mcp.example", "fourthwall_mcp_token": "t", "confirm": True},
        )

        def _boom(self: Any, *, limit: int = 50) -> Any:
            raise FourthwallError("list_products failed: connection refused")

        with patch("api.app.fourthwall.client.FourthwallReadClient.list_products", _boom):
            resp = _admin_client().post("/api/settings/integrations/test")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
        assert "connection refused" in resp.json()["error"]

    def test_test_endpoint_success(self) -> None:
        reset_cache()
        _admin_client().patch(
            "/api/settings/integrations",
            json={"fourthwall_mcp_url": "https://mcp.example", "fourthwall_mcp_token": "t", "confirm": True},
        )
        with patch(
            "api.app.fourthwall.client.FourthwallReadClient.list_products",
            lambda self, *, limit=50: [],
        ):
            resp = _admin_client().post("/api/settings/integrations/test")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# Settings store SQL (offline — no DB)
# ---------------------------------------------------------------------------

class TestSettingsSql:
    """The upsert statement must survive SQLAlchemy's bind-parameter parser."""

    def test_upsert_compiles_with_bind_params(self) -> None:
        from sqlalchemy.dialects import postgresql

        from api.app.settings_store import _upsert_statement

        statement = _upsert_statement()
        assert set(statement._bindparams) == {"key", "val"}
        compiled = str(statement.compile(dialect=postgresql.dialect()))
        # The Postgres `::` shorthand must never be emitted next to a bind
        # param — that renders as a literal `:val::jsonb` and fails at runtime.
        assert ":val::" not in compiled
        assert compiled.count("%(val)s") == 2


# ---------------------------------------------------------------------------
# Audit writer contract (offline — no DB)
# ---------------------------------------------------------------------------

def test_router_audit_calls_match_writer_signature() -> None:
    """Every `audit.record(...)` call site must use SqlAuditWriter's kwargs.

    Regression gate: the routers previously passed ``before_json=`` /
    ``after_json=`` while the writer accepts ``before=`` / ``after=``. Test
    doubles with ``**kwargs`` hid it, and the mismatch only surfaced as a 500
    against the real writer. Parsing the call sites closes that gap offline.
    """
    import ast
    import inspect
    from pathlib import Path

    from api.app.audit import SqlAuditWriter

    allowed = set(inspect.signature(SqlAuditWriter.record).parameters) - {"self"}
    routers = Path(__file__).resolve().parent.parent / "app" / "routers"

    offenders: list[tuple[str, str]] = []
    seen_calls = 0
    for path in routers.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "record"):
                continue
            seen_calls += 1
            for keyword in node.keywords:
                if keyword.arg is None:
                    offenders.append((path.name, "**kwargs"))
                elif keyword.arg not in allowed:
                    offenders.append((path.name, keyword.arg))

    assert seen_calls > 0, "expected audit.record call sites in the routers"
    assert offenders == [], offenders


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
