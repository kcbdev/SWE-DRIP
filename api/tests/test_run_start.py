"""Run-start contracts (offline — no network, no database).

`POST /api/runs` is the pipeline's only entry point: before it, the graph could
be replayed or resumed but never started, so no production run was possible.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.agents import GLOBAL_MONTHLY_CAP
from api.app.audit import get_audit_writer
from api.app.auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor, get_current_actor
from api.app.routers import runs as runs_router
from api.app.routers.runs import get_run_starter, get_spend_reader
from api.app.runs import CheckpointerRunStarter, SpendUnavailable, runs_root


class RecordingAudit:
    """Explicit signature (no **kwargs) so a bad kwarg fails the test, not prod."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record(
        self,
        *,
        actor_user_id: str,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        before: Any = None,
        after: Any = None,
    ) -> None:
        self.calls.append(
            {
                "actor_user_id": actor_user_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "before": before,
                "after": after,
            }
        )


class FakeStarter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def start(
        self,
        *,
        collection_id: str,
        design_id: Optional[str] = None,
        briefs: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {"collection_id": collection_id, "design_id": design_id, "briefs": briefs}
        )
        run_id = "run-abc"
        return {
            "run_id": run_id,
            "status": "running",
            "collection_id": collection_id,
            "design_id": design_id or run_id,
            "hitl": {"contract_approval": True, "aesthetic_qc": True},
        }


class FakeSpend:
    def __init__(self, amount: float = 0.0) -> None:
        self.amount = amount

    def month_to_date_usd(self) -> float:
        return self.amount


class BrokenSpend:
    def month_to_date_usd(self) -> float:
        raise SpendUnavailable("relation \"model_calls\" does not exist")


def build_client(
    role: str = ROLE_ADMIN, spend: Any = None
) -> tuple[TestClient, FakeStarter, RecordingAudit]:
    app = FastAPI()
    app.include_router(runs_router.router)
    starter, audit = FakeStarter(), RecordingAudit()
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", role)
    app.dependency_overrides[get_run_starter] = lambda: starter
    app.dependency_overrides[get_audit_writer] = lambda: audit
    app.dependency_overrides[get_spend_reader] = lambda: spend or FakeSpend()
    return TestClient(app, raise_server_exceptions=False), starter, audit


BODY = {"collection_id": "vibe-coding-tees"}


# ------------------------------------------------------------------- start


def test_start_returns_202_with_run_identity() -> None:
    client, starter, _ = build_client()
    response = client.post("/api/runs", json=BODY)
    assert response.status_code == 202
    data = response.json()
    assert data["collection_id"] == "vibe-coding-tees"
    assert data["status"] == "running"
    assert data["run_id"] == "run-abc"
    # A run needs a design_id; without one it is the run id (stable, unique,
    # never a fabricated business value).
    assert data["design_id"] == "run-abc"
    assert starter.calls == [
        {"collection_id": "vibe-coding-tees", "design_id": None, "briefs": None}
    ]


def test_explicit_design_id_and_briefs_are_passed_through() -> None:
    client, starter, _ = build_client()
    response = client.post(
        "/api/runs",
        json={
            "collection_id": "c-1",
            "design_id": "d-42",
            "briefs": [{"subject": "terminal", "text": "cli humor", "style": "minimal"}],
        },
    )
    assert response.status_code == 202
    assert response.json()["design_id"] == "d-42"
    assert starter.calls[0]["briefs"][0]["subject"] == "terminal"


def test_empty_collection_id_is_rejected() -> None:
    client, starter, _ = build_client()
    assert client.post("/api/runs", json={"collection_id": ""}).status_code == 422
    assert starter.calls == []


# -------------------------------------------------------------------- RBAC


@pytest.mark.parametrize("role", [ROLE_ADMIN, ROLE_OPERATOR])
def test_admin_and_operator_can_start(role: str) -> None:
    client, _, _ = build_client(role)
    assert client.post("/api/runs", json=BODY).status_code == 202


def test_viewer_cannot_start() -> None:
    client, starter, _ = build_client(ROLE_VIEWER)
    assert client.post("/api/runs", json=BODY).status_code == 403
    assert starter.calls == []


# ------------------------------------------------------------ cost guard


def test_start_refused_when_cap_reached() -> None:
    client, starter, audit = build_client(spend=FakeSpend(GLOBAL_MONTHLY_CAP))
    response = client.post("/api/runs", json=BODY)
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "budget cap" in detail
    assert str(int(GLOBAL_MONTHLY_CAP)) in detail  # both numbers named
    assert starter.calls == []  # nothing spent
    assert audit.calls == []


def test_start_refused_when_spend_cannot_be_verified() -> None:
    client, starter, _ = build_client(spend=BrokenSpend())
    response = client.post("/api/runs", json=BODY)
    assert response.status_code == 503
    assert "cannot verify" in response.json()["detail"]
    assert starter.calls == []


def test_start_allowed_below_cap() -> None:
    client, _, _ = build_client(spend=FakeSpend(GLOBAL_MONTHLY_CAP - 1))
    assert client.post("/api/runs", json=BODY).status_code == 202


# ------------------------------------------------------------------- audit


def test_start_is_audited_with_actor_and_flags() -> None:
    client, _, audit = build_client()
    client.post("/api/runs", json=BODY)
    assert len(audit.calls) == 1
    call = audit.calls[0]
    assert call["action"] == "run.start"
    assert call["entity_type"] == "run"
    assert call["entity_id"] == "run-abc"
    assert call["actor_user_id"] == "u-9"
    assert call["before"] is None
    assert call["after"]["collection_id"] == "vibe-coding-tees"
    # The HITL flags the run started with are the audit's payload.
    assert call["after"]["hitl"]["contract_approval"] is True
    assert call["after"]["spend_usd_before"] == 0.0


# ------------------------------------------------------- starter internals


class FakeGraph:
    """Records invokes; optionally signals a gate and/or raises."""

    def __init__(self, *, boom: bool = False, gate: threading.Event | None = None) -> None:
        self.boom = boom
        self.gate = gate
        self.invokes: list[dict[str, Any]] = []
        self.updated: list[dict[str, Any]] = []
        self.invoked = threading.Event()

    def invoke(self, state: Any, config: Any) -> Any:
        if self.gate is not None:
            self.gate.wait(2.0)
        if self.boom:
            self.invoked.set()
            raise RuntimeError("openrouter exploded")
        self.invokes.append({"state": state, "config": config})
        self.invoked.set()
        return {}

    def update_state(self, config: Any, values: Any) -> None:
        self.updated.append(values)


def _starter(graph: FakeGraph) -> CheckpointerRunStarter:
    return CheckpointerRunStarter(
        saver_factory=lambda: object(),  # not a context manager -> used directly
        graph_factory=lambda checkpointer=None: graph,
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The starter builds a real OpenRouterClient and reads the DB engine."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-used")
    import api.app.db as db

    monkeypatch.setattr(db, "get_engine", lambda: object())


def test_starter_config_is_phase_locked_and_settings_driven() -> None:
    graph = FakeGraph()
    started = _starter(graph).start(collection_id="c-1", design_id="d-1")
    assert graph.invoked.wait(5), "the run thread never invoked the graph"

    call = graph.invokes[0]
    configurable = call["config"]["configurable"]

    # run_id IS the checkpointer thread (NFR-1: no parallel run store).
    assert configurable["thread_id"] == started["run_id"]
    # HITL flags come from the settings store, not a request parameter.
    assert set(configurable["hitl"]) >= {"contract_approval", "aesthetic_qc", "publish_gate"}
    assert configurable["llm_client"] is not None
    assert configurable["cost_engine"] is not None
    # Render artifacts land under the root the render-serving endpoint reads.
    assert configurable["run_dir"] == str(runs_root() / "d-1")

    # PHASE LOCK (C5): nothing here may reach a storefront write.
    assert "fw_live" not in configurable
    assert "fw_client" not in configurable

    # Initial state is exactly the declared inputs.
    assert call["state"]["design_id"] == "d-1"
    assert call["state"]["collection_id"] == "c-1"
    assert call["state"]["briefs"] == []


def test_default_design_id_is_the_run_id() -> None:
    graph = FakeGraph()
    started = _starter(graph).start(collection_id="c-1")
    assert graph.invoked.wait(5), "the run thread never invoked the graph"
    assert started["design_id"] == started["run_id"]
    assert graph.invokes[0]["state"]["design_id"] == started["run_id"]


def test_start_does_not_block_on_the_graph() -> None:
    """C7: a slow graph must not hold the request/response open."""
    gate = threading.Event()
    graph = FakeGraph(gate=gate)
    started = _starter(graph).start(collection_id="c-1")
    # Returned while the graph is still blocked on the gate.
    assert started["status"] == "running"
    assert not graph.invoked.is_set()
    gate.set()
    assert graph.invoked.wait(5)


def test_graph_failure_is_recorded_into_run_state() -> None:
    """A crash must not leave a zombie 'running' row: it writes a state error."""
    graph = FakeGraph(boom=True)
    started = _starter(graph).start(collection_id="c-1")
    assert graph.invoked.wait(5)
    deadline = threading.Event()
    for _ in range(200):  # the failure is recorded after the except handler runs
        if graph.updated:
            break
        deadline.wait(0.01)
    assert graph.updated, f"no failure recorded for run {started['run_id']}"
    error = graph.updated[0]["errors"][0]
    assert "run.start failed" in error
    assert "openrouter exploded" in error


def test_runs_root_matches_the_render_serving_root() -> None:
    """A run's render is only servable if both roots agree."""
    from api.app.routers.designs import get_runs_root

    assert runs_root().resolve() == get_runs_root().resolve()
