"""Model catalog API contracts (PBI-040, spec C3).

Offline: the OpenRouter fetch is never hit — tests install a fake cache via
``model_catalog._install_test_cache`` or monkeypatch ``_fetch_live``. No
network, no database.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app import model_catalog
from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.audit import get_audit_writer
from api.app.routers.agents import router
from api.app.settings_store import reset_cache as reset_settings_cache


_FAKE_RAW = [
    {
        "id": "google/gemini-3.5-flash-lite",
        "name": "Gemini 3.5 Flash Lite",
        "context_length": 1000000,
        "pricing": {"prompt": "0.0000003", "completion": "0.0000025"},
        "architecture": {"input_modalities": ["text", "image"]},
    },
    {
        "id": "anthropic/claude-sonnet-5",
        "name": "Claude Sonnet 5",
        "context_length": 200000,
        "pricing": {"prompt": "0.000002", "completion": "0.00001"},
        "architecture": {"input_modalities": ["text", "image"]},
    },
    {
        "id": "openai/gpt-5-image-mini",
        "name": "GPT 5 Image Mini",
        "context_length": 128000,
        "pricing": {"prompt": "0.0000005", "completion": "0.000003"},
        "architecture": {"input_modalities": ["text", "image"]},
    },
]


class _NoopAudit:
    def record(self, **kwargs: Any) -> None:
        pass


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_audit_writer] = lambda: _NoopAudit()
    return app


def _client(role: str = ROLE_VIEWER) -> TestClient:
    app = _app()
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-1", "a@b.c", role)
    return TestClient(app, raise_server_exceptions=False)


def _seed() -> None:
    model_catalog.reset_cache()
    reset_settings_cache()
    model_catalog._install_test_cache(_FAKE_RAW)


# ---------------------------------------------------------------------------
# Catalog reads (offline)
# ---------------------------------------------------------------------------

class TestCatalogReads:
    def test_list_shape(self) -> None:
        _seed()
        models, status = model_catalog.list_models()
        assert len(models) == 3
        row = next(m for m in models if m["id"] == "google/gemini-3.5-flash-lite")
        assert row["name"] == "Gemini 3.5 Flash Lite"
        assert row["context_length"] == 1000000
        assert row["prompt_price_per_m"] == 0.3
        assert row["completion_price_per_m"] == 2.5
        assert "image" in row["input_modalities"]
        assert status["unavailable"] is False

    def test_filter(self) -> None:
        _seed()
        models, _ = model_catalog.list_models(query="gemini")
        assert [m["id"] for m in models] == ["google/gemini-3.5-flash-lite"]
        models, _ = model_catalog.list_models(query="CLAUDE")
        assert [m["id"] for m in models] == ["anthropic/claude-sonnet-5"]

    def test_exists_true_false(self) -> None:
        _seed()
        assert model_catalog.model_exists("google/gemini-3.5-flash-lite") is True
        assert model_catalog.model_exists("google/gemini-2.0-flash-001") is False

    def test_closest_suggests_live_id(self) -> None:
        _seed()
        suggestions = model_catalog.closest("google/gemini-2.0-flash-001")
        assert "google/gemini-3.5-flash-lite" in suggestions


# ---------------------------------------------------------------------------
# GET /api/agents/models
# ---------------------------------------------------------------------------

class TestModelsEndpoints:
    def test_list_endpoint(self) -> None:
        _seed()
        resp = _client().get("/api/agents/models")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["models"]) == 3
        assert body["unavailable"] is False
        row = body["models"][0]
        for field in ("id", "name", "context_length", "prompt_price_per_m",
                      "completion_price_per_m", "input_modalities"):
            assert field in row

    def test_list_filter_q(self) -> None:
        _seed()
        resp = _client().get("/api/agents/models", params={"q": "gemini"})
        assert resp.status_code == 200
        assert [m["id"] for m in resp.json()["models"]] == ["google/gemini-3.5-flash-lite"]

    def test_detail_endpoint(self) -> None:
        _seed()
        resp = _client().get("/api/agents/models/anthropic/claude-sonnet-5")
        assert resp.status_code == 200
        assert resp.json()["id"] == "anthropic/claude-sonnet-5"

    def test_detail_unknown_404_with_suggestions(self) -> None:
        _seed()
        resp = _client().get("/api/agents/models/google/gemini-2.0-flash-001")
        assert resp.status_code == 404
        assert "google/gemini-3.5-flash-lite" in resp.json()["detail"]["suggestions"]

    def test_viewer_can_read(self) -> None:
        _seed()
        assert _client(ROLE_VIEWER).get("/api/agents/models").status_code == 200


# ---------------------------------------------------------------------------
# PATCH model enforcement
# ---------------------------------------------------------------------------

class TestModelWriteValidation:
    def test_dead_id_rejected_with_suggestions(self) -> None:
        _seed()
        resp = _client(ROLE_ADMIN).patch(
            "/api/agents/trend_research/config",
            json={"model": "google/gemini-2.0-flash-001",
                  "cost_impact_note": "dead ID must not save"},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "google/gemini-2.0-flash-001" in detail["message"]
        assert "google/gemini-3.5-flash-lite" in detail["suggestions"]

    def test_live_id_accepted_and_roster_shows_override(self) -> None:
        _seed()
        resp = _client(ROLE_ADMIN).patch(
            "/api/agents/trend_research/config",
            json={"model": "openai/gpt-5-image-mini",
                  "cost_impact_note": "testing a live ID"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["model"] == "openai/gpt-5-image-mini"
        assert body["model_source"] == "store"

    def test_viewer_cannot_write_model(self) -> None:
        _seed()
        resp = _client(ROLE_VIEWER).patch(
            "/api/agents/trend_research/config",
            json={"model": "openai/gpt-5-image-mini",
                  "cost_impact_note": "viewer attempt"},
        )
        assert resp.status_code == 403

    def test_cap_only_patch_still_works(self) -> None:
        _seed()
        resp = _client(ROLE_ADMIN).patch(
            "/api/agents/trend_research/config",
            json={"cap_usd": 60.0, "cost_impact_note": "cap bump"},
        )
        assert resp.status_code == 200
        assert resp.json()["cap_usd"] == 60.0


# ---------------------------------------------------------------------------
# Unavailable / stale refinement rule
# ---------------------------------------------------------------------------

class TestCatalogUnavailable:
    def test_reads_empty_with_unavailable_flag(self) -> None:
        model_catalog.reset_cache()
        reset_settings_cache()
        with patch.object(model_catalog, "_fetch_live", side_effect=RuntimeError("down")):
            resp = _client().get("/api/agents/models")
            assert resp.status_code == 200
            body = resp.json()
            assert body["models"] == []
            assert body["unavailable"] is True

    def test_reads_serve_stale_cache(self) -> None:
        _seed()
        # Age the cache past the TTL, then break the network: reads serve stale.
        model_catalog._cache["fetched_at"] = time.time() - (model_catalog.TTL_SECONDS + 10)
        with patch.object(model_catalog, "_fetch_live", side_effect=RuntimeError("down")):
            models, status = model_catalog.list_models()
            assert len(models) == 3
            assert status["stale"] is True
            resp = _client().get("/api/agents/models")
            assert resp.status_code == 200
            assert len(resp.json()["models"]) == 3
            assert resp.json()["stale"] is True

    def test_stale_cache_never_authorises_write(self) -> None:
        _seed()
        model_catalog._cache["fetched_at"] = time.time() - (model_catalog.TTL_SECONDS + 10)
        with patch.object(model_catalog, "_fetch_live", side_effect=RuntimeError("down")):
            resp = _client(ROLE_ADMIN).patch(
                "/api/agents/trend_research/config",
                json={"model": "google/gemini-3.5-flash-lite",
                      "cost_impact_note": "stale must refuse"},
            )
            # Refused because the catalog cannot be verified — never accepted
            # blindly off a stale cache.
            assert resp.status_code == 503
            assert "cannot be verified" in resp.json()["detail"]

    def test_no_cache_write_reports_cannot_verify(self) -> None:
        model_catalog.reset_cache()
        reset_settings_cache()
        with patch.object(model_catalog, "_fetch_live", side_effect=RuntimeError("down")):
            resp = _client(ROLE_ADMIN).patch(
                "/api/agents/trend_research/config",
                json={"model": "google/gemini-3.5-flash-lite",
                      "cost_impact_note": "no cache must refuse"},
            )
            assert resp.status_code == 503
            assert "cannot be verified" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# PATCH params / enabled (PBI-041 API surface)
# ---------------------------------------------------------------------------

class TestParamsEnabledPatch:
    def test_params_accepted_and_roster_shows_override(self) -> None:
        _seed()
        resp = _client(ROLE_ADMIN).patch(
            "/api/agents/trend_research/config",
            json={"params": {"temperature": 0.7, "max_tokens": 1024},
                  "cost_impact_note": "cooler copy test"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["params"] == {"temperature": 0.7, "max_tokens": 1024}
        assert "params" in body["overridden"]

    def test_params_unknown_key_rejected(self) -> None:
        _seed()
        resp = _client(ROLE_ADMIN).patch(
            "/api/agents/trend_research/config",
            json={"params": {"top_p": 0.9}, "cost_impact_note": "typo key"},
        )
        assert resp.status_code == 400
        assert "top_p" in resp.json()["detail"]

    def test_params_bad_values_rejected(self) -> None:
        _seed()
        for bad in ({"temperature": 5}, {"temperature": "hot"}, {"max_tokens": 0},
                    {"max_tokens": -10}, {"max_tokens": 1.5}):
            resp = _client(ROLE_ADMIN).patch(
                "/api/agents/trend_research/config",
                json={"params": bad, "cost_impact_note": "bad value"},
            )
            assert resp.status_code == 400, bad

    def test_params_null_clears_override(self) -> None:
        _seed()
        admin = _client(ROLE_ADMIN)
        assert admin.patch(
            "/api/agents/trend_research/config",
            json={"params": {"temperature": 0.2}, "cost_impact_note": "set"},
        ).status_code == 200
        resp = admin.patch(
            "/api/agents/trend_research/config",
            json={"params": None, "cost_impact_note": "clear"},
        )
        assert resp.status_code == 200
        assert resp.json()["params"] == {}
        assert "params" not in resp.json()["overridden"]

    def test_enabled_false_disables_and_null_clears(self) -> None:
        _seed()
        admin = _client(ROLE_ADMIN)
        resp = admin.patch(
            "/api/agents/trend_research/config",
            json={"enabled": False, "cost_impact_note": "skip trend call"},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
        assert "enabled" in resp.json()["overridden"]
        resp = admin.patch(
            "/api/agents/trend_research/config",
            json={"enabled": None, "cost_impact_note": "re-enable"},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True
        assert "enabled" not in resp.json()["overridden"]

    def test_viewer_cannot_write_params(self) -> None:
        _seed()
        resp = _client(ROLE_VIEWER).patch(
            "/api/agents/trend_research/config",
            json={"params": {"temperature": 0.5}, "cost_impact_note": "viewer"},
        )
        assert resp.status_code == 403

    def test_params_write_is_audited(self) -> None:
        from api.app.audit import get_audit_writer

        _seed()
        calls: list[dict[str, Any]] = []

        class FakeAudit:
            def record(self, **kwargs: Any) -> None:
                calls.append(kwargs)

        app = _app()
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", ROLE_ADMIN)
        app.dependency_overrides[get_audit_writer] = lambda: FakeAudit()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.patch(
            "/api/agents/trend_research/config",
            json={"params": {"temperature": 0.3}, "cost_impact_note": "audit me"},
        )
        assert resp.status_code == 200
        assert len(calls) == 1
        assert calls[0]["action"] == "agents.params.update"
        assert calls[0]["after"]["params"] == {"temperature": 0.3}
