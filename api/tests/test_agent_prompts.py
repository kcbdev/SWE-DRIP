"""Prompt-override writes + prompt meta (PBI-041 remainder, spec C4).

Prompt *text* is write-only: responses carry key/version/presence only, so a
secrets-looking override can never leak through the API. Offline, no database.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app import model_catalog
from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.audit import get_audit_writer
from api.app.routers.agents import router
from api.app.settings_store import reset_cache as reset_settings_cache
from pipeline.prompts import prompt_version


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


def _reset() -> None:
    model_catalog.reset_cache()
    reset_settings_cache()


class TestPromptMeta:
    def test_qc_meta_shape(self) -> None:
        _reset()
        resp = _client().get("/api/agents/aesthetic_qc/prompt")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "node": "aesthetic_qc",
            "prompt_key": "qc_rubric",
            "base_version": "v1",
            "prompt_version": prompt_version("aesthetic_qc"),
            "has_override": False,
            "override_chars": 0,
        }

    def test_non_prompted_node_returns_nulls(self) -> None:
        _reset()
        resp = _client().get("/api/agents/placement/prompt")
        assert resp.status_code == 200
        assert resp.json()["prompt_key"] is None
        assert resp.json()["prompt_version"] is None

    def test_unknown_node_404(self) -> None:
        _reset()
        assert _client().get("/api/agents/nope/prompt").status_code == 404


class TestPromptOverrideWrite:
    def test_override_accepted_and_version_changes(self) -> None:
        _reset()
        base = prompt_version("aesthetic_qc")
        resp = _client(ROLE_ADMIN).patch(
            "/api/agents/aesthetic_qc/config",
            json={"prompt_override": "Score harshly.", "cost_impact_note": "stricter QC"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_prompt_override"] is True
        assert body["prompt_version"] == prompt_version("aesthetic_qc", "Score harshly.")
        assert body["prompt_version"] != base
        assert "prompt_override" in body["overridden"]
        # The text itself never travels back.
        assert "Score harshly." not in str(body)

    def test_meta_reflects_override(self) -> None:
        _reset()
        _client(ROLE_ADMIN).patch(
            "/api/agents/aesthetic_qc/config",
            json={"prompt_override": "Score harshly.", "cost_impact_note": "x"},
        )
        body = _client().get("/api/agents/aesthetic_qc/prompt").json()
        assert body["has_override"] is True
        assert body["override_chars"] == len("Score harshly.")

    def test_null_clears_back_to_base(self) -> None:
        _reset()
        admin = _client(ROLE_ADMIN)
        admin.patch("/api/agents/aesthetic_qc/config",
                    json={"prompt_override": "Score harshly.", "cost_impact_note": "x"})
        resp = admin.patch("/api/agents/aesthetic_qc/config",
                           json={"prompt_override": None, "cost_impact_note": "revert"})
        assert resp.status_code == 200
        assert resp.json()["has_prompt_override"] is False
        assert resp.json()["prompt_version"] == prompt_version("aesthetic_qc")

    def test_non_prompted_node_rejected(self) -> None:
        _reset()
        resp = _client(ROLE_ADMIN).patch(
            "/api/agents/placement/config",
            json={"prompt_override": "whatever", "cost_impact_note": "x"},
        )
        assert resp.status_code == 400
        assert "prompt" in resp.json()["detail"]

    def test_blank_override_rejected(self) -> None:
        _reset()
        resp = _client(ROLE_ADMIN).patch(
            "/api/agents/aesthetic_qc/config",
            json={"prompt_override": "   ", "cost_impact_note": "x"},
        )
        assert resp.status_code == 400

    def test_viewer_cannot_write(self) -> None:
        _reset()
        resp = _client(ROLE_VIEWER).patch(
            "/api/agents/aesthetic_qc/config",
            json={"prompt_override": "Score harshly.", "cost_impact_note": "x"},
        )
        assert resp.status_code == 403

    def test_audit_carries_versions_never_text(self) -> None:
        _reset()
        calls: list[dict[str, Any]] = []

        class FakeAudit:
            def record(self, **kwargs: Any) -> None:
                calls.append(kwargs)

        app = _app()
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", ROLE_ADMIN)
        app.dependency_overrides[get_audit_writer] = lambda: FakeAudit()
        client = TestClient(app, raise_server_exceptions=False)
        secret = "Score harshly with key " + "sk" + "-or-" + "testkey123"
        assert client.patch(
            "/api/agents/aesthetic_qc/config",
            json={"prompt_override": secret, "cost_impact_note": "audit me"},
        ).status_code == 200
        assert len(calls) == 1
        assert calls[0]["action"] == "agents.prompt.update"
        assert "testkey123" not in str(calls[0])
        assert calls[0]["after"]["prompt_version"] == prompt_version("aesthetic_qc", secret)

    def test_secret_text_never_echoed_anywhere(self) -> None:
        _reset()
        secret = "api_key=" + "supersecret123"
        admin = _client(ROLE_ADMIN)
        assert admin.patch(
            "/api/agents/aesthetic_qc/config",
            json={"prompt_override": secret, "cost_impact_note": "x"},
        ).status_code == 200
        for body in (
            admin.get("/api/agents").json(),
            admin.get("/api/agents/aesthetic_qc").json(),
            admin.get("/api/agents/aesthetic_qc/prompt").json(),
        ):
            assert "supersecret123" not in str(body)
