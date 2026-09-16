"""Design detail + calibration API contracts (offline, fakes)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.designs import calibration_for, design_detail_from_state
from api.app.hitl import HitlStale, InterruptInfo, get_approval_index, get_gate_source, get_graph_runner
from api.app.routers import designs as designs_router
from api.app.routers.designs import get_runs_root


def _state() -> dict[str, Any]:
    return {
        "design_id": "d-1",
        "brief": {"subject": "Rocket", "text": "mono-line rocket", "style": "terminal"},
        "collection_id": "vibe-coding",
        "collection_contract": {"collection_id": "vibe-coding", "theme": "Vibe"},
        "render_result": {"file_url": "runs/d-1/render.png", "model_used": "riverflow-v2-pro",
                          "colorways_valid": ["black"]},
        "aesthetic_qc": {"result": "pass", "scores": {"style_cohesion": 88, "focal_point": 92,
                          "placement_fit": 85, "contrast": 90},
                         "failing": [], "attempts": 1, "model_used": "m", "rubric_version": 1,
                         "pass_threshold": 70},
        "placement": {"front": "chest", "back": "none", "sleeve": "none"},
    }


def _decided(status: str = "approved") -> dict[str, Any]:
    return {"id": 3, "run_id": "run-1", "node": "aesthetic_qc", "status": status,
            "reviewer_user_id": "u-9", "note": None, "decided_at": "2026-09-14T10:00:00+00:00"}


class FakeRunner:
    def __init__(self, states: Optional[dict[str, dict]] = None) -> None:
        self.states = states if states is not None else {"run-1": _state()}

    def get_state_values(self, thread_id: str) -> dict[str, Any]:
        if thread_id not in self.states:
            raise HitlStale(thread_id)
        return self.states[thread_id]

    def resume(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("no resume on the read path")


class FakeIndex:
    def __init__(self, rows: Optional[list[dict]] = None) -> None:
        self.rows = rows if rows is not None else [_decided()]

    def list_open(self) -> list[dict[str, Any]]:
        return [r for r in self.rows if r["status"] == "pending"]

    def list_for_run(self, run_id: str) -> list[dict[str, Any]]:
        return [r for r in self.rows if r["run_id"] == run_id]

    def distinct_run_ids(self, limit: int = 50) -> list[str]:
        seen: list[str] = []
        for row in self.rows:
            if row["run_id"] not in seen:
                seen.append(row["run_id"])
        return seen[:limit]

    def get(self, item_id: int) -> Optional[dict[str, Any]]:
        return next((r for r in self.rows if r["id"] == item_id), None)


class FakeGates:
    def __init__(self, infos: Optional[list[InterruptInfo]] = None) -> None:
        self.infos = infos or []

    def list_interrupts(self) -> list[InterruptInfo]:
        return list(self.infos)


class Harness:
    def __init__(self, role: str = ROLE_VIEWER, rows=None, states=None) -> None:
        self.runner = FakeRunner(states)
        self.index = FakeIndex(rows)
        self.gates = FakeGates()
        app = FastAPI()
        app.include_router(designs_router.router)
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "op@x.y", role)
        app.dependency_overrides[get_graph_runner] = lambda: self.runner
        app.dependency_overrides[get_approval_index] = lambda: self.index
        app.dependency_overrides[get_gate_source] = lambda: self.gates
        self.client = TestClient(app, raise_server_exceptions=False)


# ------------------------------------------------------------------ detail


def test_detail_shape_from_fixture_state() -> None:
    body = Harness().client.get("/api/designs/run-1").json()
    assert body["design_id"] == "d-1" and body["run_id"] == "run-1"
    assert body["render"] == {"file_url": "runs/d-1/render.png", "model_used": "riverflow-v2-pro",
                              "colorways_valid": ["black"]}
    assert body["qc"]["scores"]["contrast"] == 90
    assert body["qc"]["result"] == "pass" and body["qc"]["rubric_version"] == 1
    assert body["qc"]["style_status"] == "unscored"  # pre-board: one spelling
    assert body["placement"]["front"] == "chest"
    assert body["context"]["brief"]["subject"] == "Rocket"
    assert body["context"]["collection_id"] == "vibe-coding"


def test_detail_missing_qc_is_null_not_synthesized() -> None:
    state = _state()
    del state["aesthetic_qc"]
    body = Harness(states={"run-1": state}).client.get("/api/designs/run-1").json()
    assert body["qc"] is None


def test_detail_unknown_is_404() -> None:
    assert Harness().client.get("/api/designs/ghost").status_code == 404


# ------------------------------------------------------------- calibration


def test_calibration_join_agrees() -> None:
    body = Harness().client.get("/api/designs/run-1/calibration").json()
    assert body["rubric"]["result"] == "pass"
    assert body["human_decisions"][0]["status"] == "approved"
    assert body["agreement"] is True


def test_calibration_disagreement() -> None:
    h = Harness(rows=[_decided("rejected")])
    body = h.client.get("/api/designs/run-1/calibration").json()
    assert body["agreement"] is False  # rubric pass vs human reject


def test_calibration_prompt_mismatch_flags_unknown() -> None:
    """A verdict recorded under an overridden prompt never looks calibrated."""
    from pipeline.prompts import prompt_version

    state = _state()
    state["aesthetic_qc"] = {**state["aesthetic_qc"], "prompt_version": "000000000000",
                             "prompt_key": "qc_rubric"}
    body = Harness(states={"run-1": state}).client.get("/api/designs/run-1/calibration").json()
    assert body["agreement"] is None
    assert "prompt changed" in body["note"]
    assert body["rubric"]["prompt_version"] == "000000000000"


def test_calibration_matching_prompt_version_agrees() -> None:
    from pipeline.prompts import prompt_version

    state = _state()
    state["aesthetic_qc"] = {**state["aesthetic_qc"],
                             "prompt_version": prompt_version("aesthetic_qc"),
                             "prompt_key": "qc_rubric"}
    body = Harness(states={"run-1": state}).client.get("/api/designs/run-1/calibration").json()
    assert body["agreement"] is True
    assert body["rubric"]["prompt_version"] == prompt_version("aesthetic_qc")


def test_calibration_without_decision_is_explicit() -> None:
    body = Harness(rows=[]).client.get("/api/designs/run-1/calibration").json()
    assert body["human_decisions"] == []
    assert body["agreement"] is None
    assert "no human decision" in body["note"]  # never implies agreement


def test_calibration_list_aggregates_runs() -> None:
    h = Harness(rows=[_decided(), {**_decided(), "id": 4, "run_id": "run-2", "status": "rejected"}])
    h.runner.states["run-2"] = _state()
    body = h.client.get("/api/calibration").json()
    by_run = {item["run_id"]: item for item in body["items"]}
    assert by_run["run-1"]["agreement"] is True
    assert by_run["run-2"]["agreement"] is False


def test_calibration_list_flags_missing_state() -> None:
    h = Harness(rows=[{**_decided(), "run_id": "gone"}])
    (item,) = [i for i in h.client.get("/api/calibration").json()["items"] if i["run_id"] == "gone"]
    assert item["rubric"]["result"] is None and item["agreement"] is None
    assert "unavailable" in item["note"]


# -------------------------------------------------------------------- roles


def test_design_endpoints_require_viewer_plus() -> None:
    assert Harness(role=ROLE_VIEWER).client.get("/api/designs/run-1").status_code == 200
    assert Harness(role=ROLE_ADMIN).client.get("/api/calibration").status_code == 200
    app = FastAPI()
    app.include_router(designs_router.router)
    client = TestClient(app)
    assert client.get("/api/designs/run-1").status_code == 401
    assert client.get("/api/calibration").status_code == 401


def test_pure_mappers_handle_empty_state() -> None:
    detail = design_detail_from_state({}, "run-9")
    assert detail["qc"] is None and detail["render"]["file_url"] is None
    joined = calibration_for(detail, [])
    assert joined["agreement"] is None


# ------------------------------------------------------------------- render


def _png_bytes() -> bytes:
    import struct

    ihdr = struct.pack(">IIBBBBB", 64, 64, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4


def test_render_serves_png_same_origin(tmp_path) -> None:
    runs = tmp_path / "runs"
    (runs / "d-1").mkdir(parents=True)
    (runs / "d-1" / "render.png").write_bytes(_png_bytes())
    state = _state()
    state["render_result"] = {"file_url": "d-1/render.png", "model_used": "m", "colorways_valid": []}
    h = Harness(states={"run-1": state})
    h.client.app.dependency_overrides[get_runs_root] = lambda: runs
    response = h.client.get("/api/designs/run-1/render")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_render_rejects_traversal_and_non_png(tmp_path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "note.txt").write_text("x")
    evil = _state()
    evil["render_result"] = {"file_url": "../../note.txt", "model_used": "m", "colorways_valid": []}
    h = Harness(states={"run-1": evil})
    h.client.app.dependency_overrides[get_runs_root] = lambda: runs
    assert h.client.get("/api/designs/run-1/render").status_code == 404
    txt = _state()
    txt["render_result"] = {"file_url": "note.txt", "model_used": "m", "colorways_valid": []}
    h2 = Harness(states={"run-1": txt})
    h2.client.app.dependency_overrides[get_runs_root] = lambda: runs
    assert h2.client.get("/api/designs/run-1/render").status_code == 404


def test_render_requires_auth(tmp_path) -> None:
    from fastapi import FastAPI as _FastAPI
    from fastapi.testclient import TestClient as _TestClient

    app = _FastAPI()
    app.include_router(designs_router.router)
    assert _TestClient(app).get("/api/designs/run-1/render").status_code == 401
