"""Runs + replay API contracts (offline, fakes)."""

from __future__ import annotations

import threading
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor, get_current_actor
from api.app.audit import get_audit_writer
from api.app.routers import runs as runs_router
from api.app.runs import NODE_STATE_KEY, RunService, Snapshot
from pipeline.routing import NODE_ORDER


def _values(visited, **extra) -> dict[str, Any]:
    base: dict[str, Any] = {"design_id": "d-1", "collection_id": "vibe-coding", "visited": list(visited)}
    base.update(extra)
    return base


def _full_values() -> dict[str, Any]:
    return _values(NODE_ORDER, **{key: {"ran": True} for key in NODE_STATE_KEY.values()})


class FakeScanner:
    def __init__(self, snaps: list[Snapshot]) -> None:
        self.snaps = snaps

    def list_snapshots(self) -> list[Snapshot]:
        return list(self.snaps)


class FakeHistory:
    def __init__(self, histories: dict[str, list[Snapshot]]) -> None:
        self.histories = histories

    def history(self, run_id: str) -> list[Snapshot]:
        return list(self.histories.get(run_id, []))


class FakeExecutor:
    """Simulates update_state+invoke: only nodes from `node` onward execute."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self.invoked: list[str] = []
        self.block: Optional[threading.Event] = None

    def replay(self, run_id: str, node: str, recorded: Any) -> dict[str, Any]:
        self.calls.append((run_id, node, recorded))
        if self.block is not None:
            self.block.wait(timeout=10)
        for name in NODE_ORDER[NODE_ORDER.index(node):]:
            self.invoked.append(name)
        return {"status": "complete", "visited_tail": list(self.invoked)}


class FakeWriter:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def record(self, **kwargs: Any) -> None:
        self.rows.append(kwargs)


def _snaps() -> list[Snapshot]:
    return [
        Snapshot("run-1", _values(["trend_research", "contract_approval"],
                                  clusters=[{"cluster_id": "c-1"}],
                                  collection_contract={"collection_id": "vibe"}),
                 "2026-09-14T10:00:00+00:00", interrupted=True),
        Snapshot("run-1", _values(["trend_research"]), "2026-09-14T09:00:00+00:00"),
        Snapshot("run-2", _full_values(), "2026-09-13T10:00:00+00:00"),
        Snapshot("run-3", _values(["trend_research"], collection_id="other"), "2026-09-14T08:00:00+00:00"),
    ]


class Harness:
    def __init__(self, role: str = ROLE_VIEWER) -> None:
        self.scanner = FakeScanner(_snaps())
        self.history = FakeHistory({
            "run-1": [Snapshot("run-1", _snaps()[0].values, "2026-09-14T10:00:00+00:00", True),
                      Snapshot("run-1", _snaps()[1].values, "2026-09-14T09:00:00+00:00")],
            "run-2": [Snapshot("run-2", _full_values(), "2026-09-13T10:00:00+00:00")],
        })
        self.executor = FakeExecutor()
        self.writer = FakeWriter()
        service = RunService(scanner=self.scanner, history=self.history,
                             executor=self.executor, writer=self.writer)
        app = FastAPI()
        app.include_router(runs_router.router)
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "op@x.y", role)
        app.dependency_overrides[runs_router.get_run_service] = lambda: service
        self.client = TestClient(app, raise_server_exceptions=False)


# ------------------------------------------------------------------ listing


def test_list_shows_current_node_status_timestamps() -> None:
    items = Harness().client.get("/api/runs").json()["items"]
    run_1 = next(i for i in items if i["id"] == "run-1")
    assert run_1["status"] == "awaiting_approval"
    assert run_1["current_node"] == "contract_approval"
    assert run_1["started_at"] == "2026-09-14T09:00:00+00:00"
    assert run_1["updated_at"] == "2026-09-14T10:00:00+00:00"
    assert next(i for i in items if i["id"] == "run-2")["status"] == "complete"


def test_list_filters() -> None:
    client = Harness().client
    assert [i["id"] for i in client.get("/api/runs", params={"collection": "vibe-coding"}).json()["items"]] == ["run-1", "run-2"]
    assert [i["id"] for i in client.get("/api/runs", params={"status": "complete"}).json()["items"]] == ["run-2"]
    assert [i["id"] for i in client.get("/api/runs", params={"date": "2026-09-14"}).json()["items"]] == ["run-1", "run-3"]


# ------------------------------------------------------------------ detail


def test_detail_maps_nodes_in_locked_order() -> None:
    body = Harness().client.get("/api/runs/run-1").json()
    assert [n["node"] for n in body["nodes"]] == NODE_ORDER  # tracker matches the graph
    reached = [n["node"] for n in body["nodes"] if n["reached"]]
    assert reached == ["trend_research", "contract_approval"]
    contract = next(n for n in body["nodes"] if n["node"] == "contract_approval")
    assert contract["state"] == {"collection_id": "vibe"}
    assert next(n for n in body["nodes"] if n["node"] == "shelf")["state"] is None


def test_detail_unknown_shape_is_flagged_not_guessed() -> None:
    h = Harness()
    h.history.histories["run-1"][0] = Snapshot(
        "run-1", _values(["trend_research", "contract_approval"], clusters=[]),
        "2026-09-14T10:00:00+00:00", True)
    contract = next(n for n in h.client.get("/api/runs/run-1").json()["nodes"]
                    if n["node"] == "contract_approval")
    assert contract["state"]["unknown_shape"] is True


def test_detail_unknown_run_is_404() -> None:
    assert Harness().client.get("/api/runs/ghost").status_code == 404


# ------------------------------------------------------------------ replay


def test_replay_skips_upstream_nodes() -> None:
    h = Harness(role=ROLE_OPERATOR)
    body = h.client.post("/api/runs/run-2/replay", json={"node": "art_render"}).json()
    assert body["status"] == "complete"
    assert h.executor.invoked == NODE_ORDER[NODE_ORDER.index("art_render"):]
    assert "trend_research" not in h.executor.invoked  # upstream never re-executed
    (call,) = h.executor.calls
    assert call[0] == "run-2" and call[1] == "art_render" and call[2] == {"ran": True}


def test_replay_writes_audit_row() -> None:
    h = Harness(role=ROLE_ADMIN)
    h.client.post("/api/runs/run-2/replay", json={"node": "placement"})
    (row,) = h.writer.rows
    assert row["action"] == "run.replay" and row["entity_id"] == "run-2"
    assert row["before"] == {"node": "placement"}


def test_replay_unknown_node_is_422() -> None:
    h = Harness(role=ROLE_OPERATOR)
    assert h.client.post("/api/runs/run-2/replay", json={"node": "nope"}).status_code == 422


def test_replay_unreached_node_is_409() -> None:
    h = Harness(role=ROLE_OPERATOR)
    assert h.client.post("/api/runs/run-1/replay", json={"node": "shelf"}).status_code == 409
    assert h.executor.calls == []


def test_duplicate_replay_returns_in_flight() -> None:
    import time

    h = Harness(role=ROLE_OPERATOR)
    h.executor.block = threading.Event()
    results: list[dict] = []
    first = threading.Thread(
        target=lambda: results.append(h.client.post("/api/runs/run-2/replay", json={"node": "shelf"}).json()))
    first.start()
    time.sleep(0.5)  # let the first replay claim in-flight
    second = h.client.post("/api/runs/run-2/replay", json={"node": "shelf"}).json()
    assert second["status"] == "in_flight"
    assert h.executor.calls and len(h.executor.calls) == 1  # never a second execution
    h.executor.block.set()
    first.join(timeout=15)


def test_replay_role_matrix() -> None:
    assert Harness(role=ROLE_VIEWER).client.post("/api/runs/run-2/replay", json={"node": "shelf"}).status_code == 403
    assert Harness(role=ROLE_OPERATOR).client.post("/api/runs/run-2/replay", json={"node": "shelf"}).status_code == 200
    app = FastAPI()
    app.include_router(runs_router.router)
    assert TestClient(app).get("/api/runs").status_code == 401
