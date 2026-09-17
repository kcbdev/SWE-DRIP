"""Mounted-route smoke: new routers resolve on the app and stay auth-gated.

Offline proof that PBI-055/056 endpoints are wired into the serving app:
every route answers 401 without a session (never 404 = mounted, never
200 = gated). Authenticated shapes live in the router contract tests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from api.app.main import app

    return TestClient(app, raise_server_exceptions=False)


class TestResearchRoutesMounted:
    def test_list_gated(self) -> None:
        assert _client().get("/api/research/runs").status_code == 401

    def test_detail_gated(self) -> None:
        assert _client().get("/api/research/runs/rsch_x").status_code == 401

    def test_logs_gated(self) -> None:
        assert _client().get("/api/research/runs/rsch_x/logs").status_code == 401

    def test_approvals_gated(self) -> None:
        assert _client().get("/api/research/approvals").status_code == 401

    def test_trigger_gated(self) -> None:
        resp = _client().post("/api/research/runs", json={"collection_slug": "vibe"})
        assert resp.status_code == 401

    def test_decide_gated(self) -> None:
        resp = _client().post("/api/research/approvals/1/decision",
                              json={"action": "approve"})
        assert resp.status_code == 401


class TestStylesRoutesMounted:
    def test_list_gated(self) -> None:
        assert _client().get("/api/styles").status_code == 401

    def test_create_gated(self) -> None:
        resp = _client().post("/api/styles", json={
            "name": "x", "graphic_definition": "y", "expected_version": 1})
        assert resp.status_code == 401

    def test_update_gated(self) -> None:
        resp = _client().patch("/api/styles/mono-log", json={"expected_version": 1})
        assert resp.status_code == 401

    def test_delete_refused_loudly(self) -> None:
        # 405 (not 404/401): the route exists and refuses by design. Auth runs
        # first in the stack, so an unauthenticated DELETE still 401s — the
        # 405 shape itself is covered authenticated in test_styles_api.py.
        assert _client().delete("/api/styles/mono-log").status_code in (401, 405)


class TestBoardRouteMounted:
    def test_board_gated(self) -> None:
        assert _client().get("/api/collections/vibe/board/board.png").status_code == 401
