"""HITL resume service + approvals API contracts (offline, fakes + one real scan)."""

from __future__ import annotations

from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor, get_current_actor
from api.app.hitl import (
    HitlAmbiguous,
    HitlStale,
    HitlUnknownNode,
    InterruptInfo,
    build_resume_payload,
    entity_ref,
    get_approval_index,
    get_audit_writer,
    get_gate_source,
    get_graph_runner,
)
from api.app.routers import approvals as approvals_router


def _contract_info(run_id: str = "run-1") -> InterruptInfo:
    return InterruptInfo(
        run_id=run_id,
        node="contract_approval",
        payload={
            "node": "contract_approval",
            "status": "awaiting_approval",
            "contracts": [{"collection_id": "vibe-coding", "theme": "Vibe Coding"}],
        },
        interrupt_id="i-1",
        waiting_since="2026-09-13T10:00:00+00:00",
    )


def _publish_info(run_id: str = "run-2") -> InterruptInfo:
    return InterruptInfo(
        run_id=run_id,
        node="publish_gate",
        payload={
            "node": "publish_gate",
            "status": "awaiting_approval",
            "product": {"id": "fw-1", "title": "Vibe Tee", "state": "DRAFT"},
        },
        interrupt_id="i-2",
        waiting_since="2026-09-13T11:00:00+00:00",
    )


class FakeGates:
    def __init__(self, infos: list[InterruptInfo]) -> None:
        self.infos = infos

    def list_interrupts(self) -> list[InterruptInfo]:
        return list(self.infos)


class FakeIndex:
    def __init__(self) -> None:
        self.rows: dict[int, dict[str, Any]] = {}
        self._next = 1

    def list_open(self) -> list[dict[str, Any]]:
        return [r for r in self.rows.values() if r["status"] == "pending"]

    def get(self, item_id: int) -> Optional[dict[str, Any]]:
        return self.rows.get(item_id)

    def ensure_pending(self, run_id: str, node: str) -> dict[str, Any]:
        for row in self.rows.values():
            if row["run_id"] == run_id and row["node"] == node and row["status"] == "pending":
                return row
        row = {"id": self._next, "run_id": run_id, "node": node, "status": "pending",
               "reviewer_user_id": None, "note": None, "decided_at": None}
        self.rows[self._next] = row
        self._next += 1
        return row

    def claim(self, item_id: int, *, status: str, reviewer_user_id: str, note: Optional[str]):
        row = self.rows.get(item_id)
        if row is None or row["status"] != "pending":
            return None
        row.update({"status": status, "reviewer_user_id": reviewer_user_id, "note": note,
                    "decided_at": "2026-09-13T12:00:00+00:00"})
        return row

    def reopen(self, item_id: int) -> None:
        row = self.rows.get(item_id)
        if row is not None and row["status"] != "pending":
            row.update({"status": "pending", "reviewer_user_id": None, "note": None, "decided_at": None})


class FakeRunner:
    def __init__(self, values: dict[str, dict], fail_resume: bool = False) -> None:
        self.values = values
        self.resumes: list[tuple[str, dict]] = []
        self.fail_resume = fail_resume

    def get_state_values(self, thread_id: str) -> dict[str, Any]:
        if thread_id not in self.values:
            raise HitlStale(f"run state unavailable for {thread_id!r}")
        return self.values[thread_id]

    def resume(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.fail_resume:
            raise RuntimeError("graph down")
        self.resumes.append((thread_id, payload))
        return {"thread_id": thread_id}


class FakeWriter:
    def __init__(self, fail: bool = False) -> None:
        self.rows: list[dict] = []
        self.fail = fail

    def record(self, **kwargs) -> None:
        if self.fail:
            raise RuntimeError("audit store down")
        self.rows.append(kwargs)


class Harness:
    def __init__(self, role: str = ROLE_ADMIN, infos=None, values=None) -> None:
        self.gates = FakeGates(infos if infos is not None else [_contract_info(), _publish_info()])
        self.index = FakeIndex()
        self.runner = FakeRunner(values if values is not None else {
            "run-1": {"clusters": [{"cluster_id": "cluster-1"}]},
            "run-2": {"design_id": "d-2"},
        })
        self.writer = FakeWriter()
        app = FastAPI()
        app.include_router(approvals_router.router)
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "op@x.y", role)
        app.dependency_overrides[get_gate_source] = lambda: self.gates
        app.dependency_overrides[get_approval_index] = lambda: self.index
        app.dependency_overrides[get_graph_runner] = lambda: self.runner
        app.dependency_overrides[get_audit_writer] = lambda: self.writer
        self.client = TestClient(app, raise_server_exceptions=False)


# ------------------------------------------------------------- queue (C1)


def test_queue_aggregation_shape() -> None:
    body = Harness(role=ROLE_VIEWER).client.get("/api/approvals").json()
    items = body["items"]
    assert len(items) == 2
    contract, publish = items
    assert contract["run_id"] == "run-1" and contract["status"] == "pending"
    assert contract["entity_ref"] == {"type": "collection_contract", "id": "vibe-coding", "label": "Vibe Coding"}
    assert contract["waiting_since"] == "2026-09-13T10:00:00+00:00"
    assert publish["entity_ref"]["type"] == "product"


def test_queue_requires_auth() -> None:
    app = FastAPI()
    app.include_router(approvals_router.router)
    assert TestClient(app).get("/api/approvals").status_code == 401


# --------------------------------------------------- decisions (C2/C4/C6)


def test_approve_publish_resumes_exactly_once() -> None:
    h = Harness()
    item_id = h.client.get("/api/approvals").json()["items"][1]["id"]
    response = h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved" and body["resumed"] is True
    assert h.runner.resumes == [("run-2", {"approved": True})]


def test_double_submit_is_idempotent() -> None:
    h = Harness()
    item_id = h.client.get("/api/approvals").json()["items"][1]["id"]
    first = h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"}).json()
    second = h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"}).json()
    assert first["status"] == second["status"] == "approved"
    assert second["resumed"] is False
    assert len(h.runner.resumes) == 1  # never double-resumed
    assert len(h.writer.rows) == 1  # never double-audited


def test_viewer_cannot_decide() -> None:
    h = Harness(role=ROLE_VIEWER)
    item_id = h.client.get("/api/approvals").json()["items"][0]["id"]
    assert h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"}).status_code == 403


def test_operator_can_decide() -> None:
    h = Harness(role=ROLE_OPERATOR)
    item_id = h.client.get("/api/approvals").json()["items"][0]["id"]
    assert h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"}).status_code == 200


def test_decide_requires_auth() -> None:
    app = FastAPI()
    app.include_router(approvals_router.router)
    assert TestClient(app).post("/api/approvals/1/decision", json={"action": "approve"}).status_code == 401


def test_decision_writes_audit_row() -> None:
    h = Harness()
    item_id = h.client.get("/api/approvals").json()["items"][1]["id"]
    h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "reject", "note": "off-brand"})
    (row,) = h.writer.rows
    assert row["actor_user_id"] == "u-9"
    assert row["action"] == "approval.reject"
    assert row["entity_type"] == "approval" and row["entity_id"] == str(item_id)
    assert row["before"] == {"status": "pending"}
    assert row["after"] == {"status": "rejected", "note": "off-brand"}


def test_reject_publish_resumes_negative_and_stays_draft() -> None:
    h = Harness()
    item_id = h.client.get("/api/approvals").json()["items"][1]["id"]
    body = h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "reject"}).json()
    assert body["status"] == "rejected"
    assert h.runner.resumes == [("run-2", {"approved": False})]


def test_contract_single_cluster_approve() -> None:
    h = Harness()
    item_id = h.client.get("/api/approvals").json()["items"][0]["id"]
    body = h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"}).json()
    assert body["status"] == "approved"
    assert h.runner.resumes == [("run-1", {"approved_cluster_id": "cluster-1"})]


def test_contract_multi_cluster_approve_needs_selection() -> None:
    values = {"run-1": {"clusters": [{"cluster_id": "c-a"}, {"cluster_id": "c-b"}]}}
    h = Harness(values=values)
    item_id = h.client.get("/api/approvals").json()["items"][0]["id"]
    response = h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"})
    assert response.status_code == 422
    assert "approved_cluster_id" in response.json()["detail"]
    assert h.runner.resumes == []  # nothing resumed on ambiguous input
    ok = h.client.post(
        f"/api/approvals/{item_id}/decision",
        json={"action": "approve", "selection": {"approved_cluster_id": "c-b"}},
    )
    assert ok.status_code == 200
    assert h.runner.resumes == [("run-1", {"approved_cluster_id": "c-b"})]


def test_unknown_item_is_404() -> None:
    assert Harness().client.post("/api/approvals/999/decision", json={"action": "approve"}).status_code == 404


def test_bad_action_is_422() -> None:
    h = Harness()
    item_id = h.client.get("/api/approvals").json()["items"][0]["id"]
    assert h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "launch"}).status_code == 422


def test_stale_run_is_409_and_resumes_nothing() -> None:
    h = Harness(values={})  # runner knows no threads
    item_id = h.client.get("/api/approvals").json()["items"][0]["id"]
    response = h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"})
    assert response.status_code == 409
    assert h.runner.resumes == []


def test_resume_failure_reopens_for_retry() -> None:
    h = Harness()
    h.runner.fail_resume = True
    item_id = h.client.get("/api/approvals").json()["items"][1]["id"]
    assert h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"}).status_code == 500
    assert h.index.get(item_id)["status"] == "pending"  # rolled back, retryable
    h.runner.fail_resume = False
    retry = h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"}).json()
    assert retry["status"] == "approved" and retry["resumed"] is True
    assert len(h.runner.resumes) == 1  # the failed attempt never completed


# ------------------------------------------------------------------ units


def test_audit_failure_after_resume_keeps_claim() -> None:
    """Resume succeeded but audit failed: no reopen (retry must not double-resume)."""
    h = Harness()
    h.writer.fail = True
    item_id = h.client.get("/api/approvals").json()["items"][1]["id"]
    assert h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"}).status_code == 500
    assert h.index.get(item_id)["status"] == "approved"  # claim kept, not reopened
    h.writer.fail = False
    replay = h.client.post(f"/api/approvals/{item_id}/decision", json={"action": "approve"}).json()
    assert replay["resumed"] is False
    assert len(h.runner.resumes) == 1  # exactly once, despite the retry


def test_crash_recovery_relists_decided_gate() -> None:
    """Hard crash between claim and resume: re-list surfaces a fresh row."""
    h = Harness()
    items = h.client.get("/api/approvals").json()["items"]
    decided = h.index.claim(items[1]["id"], status="approved", reviewer_user_id="u-9", note=None)
    assert decided is not None
    fresh = h.client.get("/api/approvals").json()["items"]
    assert any(i["status"] == "pending" and i["run_id"] == "run-2" for i in fresh)
    new_id = next(i["id"] for i in fresh if i["run_id"] == "run-2" and i["status"] == "pending")
    body = h.client.post(f"/api/approvals/{new_id}/decision", json={"action": "approve"}).json()
    assert body["status"] == "approved" and body["resumed"] is True


def test_decide_refuses_consumed_gate() -> None:
    """Pending row but no live interrupt: 409, no resume, row stays pending."""
    h = Harness(infos=[])  # gate gone, stale row remains
    row = h.index.ensure_pending("run-9", "publish_gate")
    response = h.client.post(f"/api/approvals/{row['id']}/decision", json={"action": "approve"})
    assert response.status_code == 409
    assert h.runner.resumes == []
    assert h.index.get(row["id"])["status"] == "pending"


def test_queue_items_carry_cluster_options() -> None:
    h = Harness()
    items = h.client.get("/api/approvals").json()["items"]
    assert items[0]["clusters"] == [{"cluster_id": "cluster-1"}]
    assert items[1].get("clusters", []) == []


def test_index_metadata_enforces_single_open_row() -> None:
    from api.app.models import hitl_approvals as table

    matches = [ix for ix in table.indexes if ix.name == "uq_hitl_approvals_open"]
    assert len(matches) == 1 and matches[0].unique
    where = matches[0].dialect_options["postgresql"]["where"]
    assert where is not None and "pending" in str(where)


def test_entity_ref_shapes() -> None:
    assert entity_ref("contract_approval", {"contracts": [{"collection_id": "c", "theme": "T"}]}) == {
        "type": "collection_contract", "id": "c", "label": "T"}
    assert entity_ref("publish_gate", {"product": {"id": "p", "title": "T"}})["type"] == "product"
    assert entity_ref("aesthetic_qc", {"failing": ["contrast"], "attempts": 3})["label"] == "failing: contrast"


def test_resume_payload_unknown_node_is_loud() -> None:
    with pytest.raises(HitlUnknownNode):
        build_resume_payload("shelf", "approve")
    with pytest.raises(HitlAmbiguous):
        build_resume_payload("contract_approval", "approve", clusters=[])


def test_gate_source_lists_live_interrupts_without_mocks() -> None:
    """The checkpointer scan works against a real saver + graph (MemorySaver)."""
    from langgraph.checkpoint.memory import MemorySaver

    from api.app.hitl import CheckpointerGateSource
    from pipeline.graph import build_graph

    saver = MemorySaver()
    graph = build_graph(checkpointer=saver)
    graph.invoke({"design_id": "scan-me"}, {"configurable": {"thread_id": "scan-t"}})
    source = CheckpointerGateSource(saver_factory=lambda: saver, graph_factory=build_graph)
    found = source.list_interrupts()
    assert len(found) == 1
    assert found[0].run_id == "scan-t" and found[0].node == "publish_gate"
    assert found[0].payload["node"] == "publish_gate"
    assert found[0].waiting_since
