"""Per-node run-log endpoints (PBI-042, spec C7) — offline, fakes."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.routers import runs as runs_router
from api.app.runs import RunService, Snapshot
from api.app.stream import StreamBroker, is_run_log_event


def _values(visited, **extra) -> dict[str, Any]:
    base: dict[str, Any] = {"design_id": "d-1", "collection_id": "vibe-coding",
                            "visited": list(visited)}
    base.update(extra)
    return base


class FakeHistory:
    def __init__(self, histories: dict[str, list[Snapshot]]) -> None:
        self.histories = histories

    def history(self, run_id: str) -> list[Snapshot]:
        return list(self.histories.get(run_id, []))


class FakeService:
    """Minimal run_detail: known runs resolve, anything else is KeyError."""

    def __init__(self, known: set[str]) -> None:
        self.known = known

    def run_detail(self, run_id: str) -> dict[str, Any]:
        if run_id not in self.known:
            raise KeyError(f"unknown run {run_id}")
        return {"id": run_id}


class FakeLogReader:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    def for_run(self, run_id: str, *, node: Optional[str] = None,
                level: Optional[str] = None, since: Optional[str] = None,
                limit: int = 500) -> list[dict[str, Any]]:
        self.calls.append({"run_id": run_id, "node": node, "level": level,
                           "since": since, "limit": limit})
        out = [r for r in self.rows if r["run_id"] == run_id]
        if node is not None:
            out = [r for r in out if r["node"] == node]
        if level is not None:
            out = [r for r in out if r["level"] == level]
        if since is not None:
            out = [r for r in out if r["ts"] >= since]
        return out[:limit]


ROWS = [
    {"run_id": "run-1", "node": "trend_research", "level": "info",
     "message": "clustering 2 briefs", "detail": {}, "ts": "2026-09-16T00:00:01+00:00"},
    {"run_id": "run-1", "node": "trend_research", "level": "warn",
     "message": "cost row not recorded", "detail": {}, "ts": "2026-09-16T00:00:02+00:00"},
    {"run_id": "run-1", "node": "shelf", "level": "error",
     "message": "rejected run: collection 'vibe' is not active",
     "detail": {}, "ts": "2026-09-16T00:00:03+00:00"},
    {"run_id": "run-2", "node": "shelf", "level": "info",
     "message": "accepted", "detail": {}, "ts": "2026-09-16T00:00:04+00:00"},
]


def _client(role: str = ROLE_VIEWER, reader: FakeLogReader | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(runs_router.router)
    log_reader = reader or FakeLogReader(ROWS)
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "op@x.y", role)
    app.dependency_overrides[runs_router.get_run_service] = lambda: FakeService({"run-1", "run-2"})
    app.dependency_overrides[runs_router.get_log_reader] = lambda: log_reader
    return TestClient(app, raise_server_exceptions=False)


class TestGetRunLogs:
    def test_returns_run_rows(self) -> None:
        body = _client().get("/api/runs/run-1/logs").json()
        assert len(body["items"]) == 3
        assert body["items"][0]["node"] == "trend_research"

    def test_node_filter(self) -> None:
        body = _client().get("/api/runs/run-1/logs", params={"node": "shelf"}).json()
        assert [i["message"] for i in body["items"]] == ["rejected run: collection 'vibe' is not active"]

    def test_level_filter(self) -> None:
        body = _client().get("/api/runs/run-1/logs", params={"level": "error"}).json()
        assert len(body["items"]) == 1

    def test_since_and_limit(self) -> None:
        body = _client().get("/api/runs/run-1/logs",
                             params={"since": "2026-09-16T00:00:02+00:00", "limit": 1}).json()
        assert len(body["items"]) == 1
        assert body["items"][0]["level"] == "warn"

    def test_unknown_run_404(self) -> None:
        assert _client().get("/api/runs/ghost/logs").status_code == 404

    def test_bad_since_422(self) -> None:
        resp = _client().get("/api/runs/run-1/logs", params={"since": "not-a-time"})
        assert resp.status_code == 422

    def test_failed_node_reason_visible(self) -> None:
        body = _client().get("/api/runs/run-1/logs", params={"level": "error"}).json()
        assert "not active" in body["items"][0]["message"]

    def test_viewer_can_read_admin_route_shape(self) -> None:
        assert _client(ROLE_VIEWER).get("/api/runs/run-1/logs").status_code == 200
        app = FastAPI()
        app.include_router(runs_router.router)
        assert TestClient(app).get("/api/runs/run-1/logs").status_code == 401


class TestRunLogStreamFilter:
    def test_only_matching_run_log_events_pass(self) -> None:
        assert is_run_log_event({"type": "run.log", "run_id": "a"}, "a") is True
        assert is_run_log_event({"type": "run.log", "run_id": "b"}, "a") is False
        assert is_run_log_event({"type": "queue.delta", "run_id": "a"}, "a") is False
        assert is_run_log_event({}, "a") is False

    def test_broker_fans_out_run_log(self) -> None:
        broker = StreamBroker()
        queue = broker.new_subscriber()
        try:
            delivered = broker.publish_run_log("run-1", "shelf", "error", "rejected", "ts")
            assert delivered == 1
            event = queue.get_nowait()
            assert is_run_log_event(event, "run-1") is True
            assert is_run_log_event(event, "run-2") is False
        finally:
            broker.unsubscribe(queue)

    def test_stream_route_registered(self) -> None:
        paths = [getattr(r, "path", "") for r in runs_router.router.routes]
        assert "/api/runs/{run_id}/logs" in paths
        assert "/api/runs/{run_id}/logs/stream" in paths


class TestRunDetailConfigSummary:
    def test_detail_carries_trimmed_node_config(self) -> None:
        history = FakeHistory({
            "run-1": [Snapshot("run-1", _values(
                ["trend_research"],
                node_config={"trend_research": {"model": "m-1", "params": {"temperature": 0.5},
                                                "prompt_override": "secret-text", "enabled": False,
                                                "overridden": ["model"]}},
            ), "2026-09-16T00:00:00+00:00")],
        })

        from api.app.runs import RunService

        class _Writer:
            def record(self, **kwargs: Any) -> None:
                pass

        service = RunService(scanner=None, history=history, executor=None, writer=_Writer())  # type: ignore[arg-type]
        detail = service.run_detail("run-1")
        trend = detail["node_config"]["trend_research"]
        assert trend == {"model": "m-1", "params": {"temperature": 0.5}, "enabled": False}
        # Prompt text never travels in the run payload.
        assert "secret-text" not in str(detail)
        assert detail["node_config"]["shelf"] == {"model": None, "params": {}, "enabled": True}
