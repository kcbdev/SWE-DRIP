"""Research-run API contracts (PBI-055, spec C4/C6) — offline, fakes + MemorySaver."""

from __future__ import annotations

import json
import shutil
import struct
import time
from pathlib import Path
from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from api.app.agents import GLOBAL_MONTHLY_CAP
from api.app.audit import get_audit_writer
from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.collections_store import CollectionNotFound, CollectionsStore
from api.app.hitl import (
    CheckpointerGateSource,
    HitlAmbiguous,
    HitlService,
    HitlUnknownNode,
    build_resume_payload,
    entity_ref,
)
from api.app.inspiration import InspirationStore
from api.app.research_runs import (
    ResearchGraphRunner,
    ResearchRunPorts,
    ResearchRunStarter,
    build_research_state,
    derive_research_status,
    is_research_run,
    list_research_runs,
    research_node_detail,
    research_run_detail,
    summarize_research,
)
from api.app.routers import research as research_router
from api.app.runs import RunService, Snapshot, SpendUnavailable
from pipeline.collection_graph import RESEARCH_ORDER, RESEARCH_RUN_PREFIX, build_collection_graph
from pipeline.runlog import MemoryRunLogger

PNG = (
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    + b"\x00\x00\x00\x0dIHDR" + b"\x00" * 13
)


def _png_bytes(width: int = 256, height: int = 256) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr
            + b"\x00" * 4 + b"\x00\x00\x00\x00IEND")


GOOD_DIRECTIVES = {
    "style_descriptors": ["mono-line", "flat fills"],
    "motifs": ["git branches", "conflict markers"],
    "palette_justification": "terminal greens on void black",
    "avoid": ["photorealism"],
}


class _Reply:
    def __init__(self, content: Any) -> None:
        self.content = content
        self.raw: dict[str, Any] = {"usage": {"prompt_tokens": 3, "completion_tokens": 7}}


class _StubClient:
    def __init__(self, chat_content: str = "") -> None:
        self._chat_content = chat_content
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> _Reply:
        self.calls.append({"kind": "chat", **kwargs})
        return _Reply(self._chat_content)

    def image(self, **kwargs: Any) -> _Reply:
        self.calls.append({"kind": "image", **kwargs})
        return _Reply(_png_bytes())


class _FakeEngine:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    class _Conn:
        def __init__(self, outer: "_FakeEngine") -> None:
            self._outer = outer

        def execute(self, stmt: Any) -> None:
            self._outer.rows.append(dict(stmt.compile().params))

        def __enter__(self) -> "_FakeEngine._Conn":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    def begin(self) -> "_FakeEngine._Conn":
        return self._Conn(self)


class _NoopAudit:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.rows.append(kwargs)


class _FakeSpend:
    def __init__(self, spent: float = 0.0, broken: bool = False) -> None:
        self.spent = spent
        self.broken = broken

    def month_to_date_usd(self) -> float:
        if self.broken:
            raise SpendUnavailable("db down")
        return self.spent


class _FakeReader:
    def __init__(self, rows: Optional[list[dict[str, Any]]] = None) -> None:
        self.rows = rows or []

    def for_run(self, run_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        return [r for r in self.rows if r.get("run_id") == run_id]


class _FakeStarter:
    def __init__(self, result: Optional[dict[str, Any]] = None,
                 error: Optional[BaseException] = None) -> None:
        self.result = result or {"run_id": "rsch_abc", "status": "started",
                                 "collection_slug": "vibe"}
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def start(self, *, collection_slug: str, actor_user_id: str = "") -> dict[str, Any]:
        self.calls.append({"collection_slug": collection_slug, "actor_user_id": actor_user_id})
        if self.error is not None:
            raise self.error
        return dict(self.result)


class _FakePorts:
    def __init__(self, snaps: Optional[list[Snapshot]] = None) -> None:
        self.snaps = snaps or []

    def list_research_snapshots(self) -> list[Snapshot]:
        return list(self.snaps)

    def history(self, run_id: str) -> list[Snapshot]:
        return [s for s in self.snaps if s.run_id == run_id]


class _FakeIndex:
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
                    "decided_at": "2026-09-17T00:00:00+00:00"})
        return row

    def reopen(self, item_id: int) -> None:
        row = self.rows.get(item_id)
        if row is not None and row["status"] != "pending":
            row.update({"status": "pending", "reviewer_user_id": None, "note": None,
                        "decided_at": None})


def _snap(run_id: str, values: dict[str, Any], interrupted: bool = False) -> Snapshot:
    return Snapshot(run_id=run_id, values=values, at="2026-09-17T00:00:00+00:00",
                    interrupted=interrupted)


def _collections(tmp_path: Path) -> CollectionsStore:
    store = CollectionsStore(tmp_path / "collections")
    store.create({
        "collection_id": "vibe", "theme": "Vibe", "status": "draft",
        "style_archetype": "mono-log",
        "illustration_rules": {"line_weight": None, "palette": ["#0D0D0D"],
                               "no_mixed_styles": True},
        "garment_colorways": [], "placement_templates": [],
        "product_count_target": None, "lifecycle_days": None,
        "kpi_thresholds": {"min_units": None, "min_conversion": None,
                           "eval_window_days": None},
        "created_by": "u-9", "created_at": "2026-09-16T00:00:00+00:00",
        "approved_at": None, "retired_at": None, "survivor_products": [],
    })
    return store


def _seeded_inspiration(tmp_path: Path, store: CollectionsStore) -> InspirationStore:
    insp = InspirationStore(tmp_path / "collections", store)
    insp.add_asset("vibe", PNG, "image/png", note="line quality", actor_user_id="u-9")
    return insp


class TestNamespace:
    def test_prefix_constant(self) -> None:
        assert RESEARCH_RUN_PREFIX == "rsch_"
        assert is_research_run("rsch_abc")
        assert not is_research_run("abc123")
        assert not is_research_run("")

    def test_item_list_skips_research_threads(self) -> None:
        from api.app.runs import RunService

        class Scanner:
            def list_snapshots(self) -> list[Snapshot]:
                return [
                    _snap("run-1", {"visited": [], "collection_id": "vibe"}),
                    _snap("rsch_9", {"visited": ["inspiration_review"],
                                     "collection_slug": "vibe"}, interrupted=True),
                ]

        class Ports(Scanner):
            def history(self, run_id: str) -> list[Snapshot]:
                return [s for s in self.list_snapshots() if s.run_id == run_id]

        svc = RunService(scanner=Ports(), history=Ports(), executor=None, writer=None)  # type: ignore[arg-type]
        rows = svc.list_runs()
        assert [r["id"] for r in rows] == ["run-1"]

    def test_item_detail_rejects_research_id(self) -> None:
        from api.app.runs import RunService

        class Ports:
            def list_snapshots(self) -> list[Snapshot]:
                return []

            def history(self, run_id: str) -> list[Snapshot]:
                return [_snap(run_id, {"visited": []})]

        svc = RunService(scanner=Ports(), history=Ports(), executor=None, writer=None)  # type: ignore[arg-type]
        with pytest.raises(KeyError):
            svc.run_detail("rsch_9")

    def test_research_ports_ignore_item_threads(self, tmp_path: Path) -> None:
        saver = MemorySaver()
        ports = ResearchRunPorts(saver_factory=lambda: saver)
        assert ports.list_research_snapshots() == []
        assert ports.history("run-1") == []


class TestStatusDerivation:
    def test_matrix(self) -> None:
        assert derive_research_status({}, False) == "started"
        assert derive_research_status({"visited": ["inspiration_review"]}, False) == "started"
        assert derive_research_status({"visited": ["inspiration_review", "style_synthesis"]}, False) == "synthesizing"
        assert derive_research_status(
            {"visited": ["inspiration_review", "style_synthesis", "mood_board"]}, False) == "board_rendering"
        assert derive_research_status({"visited": ["inspiration_review"]}, True) == "awaiting_approval"
        assert derive_research_status({"visited": [], "errors": ["boom"]}, False) == "failed"
        full = {"visited": list(RESEARCH_ORDER)}
        assert derive_research_status(full, False) == "complete"

    def test_node_detail_unknown_shape(self) -> None:
        history = [_snap("rsch_1", {"visited": ["mood_board"]})]
        detail = research_node_detail(history)
        assert [d["node"] for d in detail] == RESEARCH_ORDER
        assert detail[0]["reached"] is False
        assert detail[2]["reached"] is True
        assert detail[2]["state"]["unknown_shape"] is True

    def test_summary_shape(self) -> None:
        row = summarize_research("rsch_1", {"visited": ["mood_board"],
                                            "collection_slug": "vibe",
                                            "board": {"board_version": 2},
                                            "diversity_flags": ["f1"]}, False, None, None)
        assert row["id"] == "rsch_1"
        assert row["current_stage"] == "board_rendering"
        assert row["board_version"] == 2
        assert row["diversity_flags"] == ["f1"]


class TestGateMapping:
    def test_approve_reject_regenerate(self) -> None:
        assert build_resume_payload("collection_gate", "approve") == {"approved": True}
        assert build_resume_payload("collection_gate", "approve", note="go") == {
            "approved": True, "note": "go"}
        assert build_resume_payload("collection_gate", "reject") == {"approved": False}
        assert build_resume_payload("collection_gate", "regenerate") == {"approved": False}

    def test_edit_and_approve_rides_selection(self) -> None:
        payload = build_resume_payload("collection_gate", "approve",
                                       selection={"contract": {"theme": "CEO"}})
        assert payload == {"approved": True, "contract": {"theme": "CEO"}}

    def test_contract_rejected_loudly(self) -> None:
        with pytest.raises(HitlAmbiguous):
            build_resume_payload("collection_gate", "approve", selection={"contract": {}})
        with pytest.raises(HitlAmbiguous):
            build_resume_payload("collection_gate", "reject",
                                 selection={"contract": {"theme": "x"}})
        with pytest.raises(HitlUnknownNode):
            build_resume_payload("nope", "approve")

    def test_entity_ref(self) -> None:
        ref = entity_ref("collection_gate", {"draft": {"collection_id": "vibe", "theme": "V"}})
        assert ref == {"type": "research_gate", "id": "vibe", "label": "V"}


class TestBuildState:
    def test_unknown_slug(self, tmp_path: Path) -> None:
        store = _collections(tmp_path)
        insp = InspirationStore(tmp_path / "collections", store)
        with pytest.raises(CollectionNotFound):
            build_research_state(store, insp, "ghost")

    def test_empty_inspiration_refused(self, tmp_path: Path) -> None:
        store = _collections(tmp_path)
        insp = InspirationStore(tmp_path / "collections", store)
        with pytest.raises(ValueError, match="no inspiration curated"):
            build_research_state(store, insp, "vibe")

    def test_happy_path_seeds_graph_keys(self, tmp_path: Path) -> None:
        store = _collections(tmp_path)
        insp = _seeded_inspiration(tmp_path, store)
        state = build_research_state(store, insp, "vibe")
        assert state["collection_slug"] == "vibe"
        assert state["collection_theme"] == "Vibe"
        assert state["style_archetype"] == "mono-log"
        assert len(state["inspiration"]["assets"]) == 1
        assert isinstance(state["avoid"], list) and isinstance(state["lineage"], dict)


def _research_client(role: str = ROLE_ADMIN, starter=None, ports=None,
                     spend: float = 0.0, spend_broken: bool = False,
                     reader_rows: Optional[list[dict[str, Any]]] = None) -> tuple[TestClient, _NoopAudit]:
    audit = _NoopAudit()
    app = FastAPI()
    app.include_router(research_router.router)
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", role)
    app.dependency_overrides[get_audit_writer] = lambda: audit
    app.dependency_overrides[research_router.get_research_starter] = lambda: starter or _FakeStarter()
    app.dependency_overrides[research_router.get_research_ports] = lambda: ports or _FakePorts()
    app.dependency_overrides[research_router.get_spend_reader] = lambda: _FakeSpend(spend, spend_broken)
    app.dependency_overrides[research_router.get_log_reader] = lambda: _FakeReader(reader_rows)
    return TestClient(app, raise_server_exceptions=False), audit


class TestTrigger:
    def test_start_202_and_audited(self) -> None:
        client, audit = _research_client(starter=_FakeStarter())
        body = client.post("/api/research/runs", json={"collection_slug": "vibe"}).json()
        assert body["run_id"] == "rsch_abc" and body["status"] == "started"
        assert audit.rows and audit.rows[0]["action"] == "research.start"
        assert audit.rows[0]["entity_id"] == "rsch_abc"

    def test_empty_slug_422(self) -> None:
        client, _ = _research_client()
        assert client.post("/api/research/runs", json={"collection_slug": " "}).status_code == 422

    def test_unknown_collection_404(self) -> None:
        client, _ = _research_client(starter=_FakeStarter(error=CollectionNotFound("ghost")))
        assert client.post("/api/research/runs", json={"collection_slug": "ghost"}).status_code == 404

    def test_empty_inspiration_422(self) -> None:
        client, _ = _research_client(starter=_FakeStarter(error=ValueError("no inspiration curated")))
        assert client.post("/api/research/runs", json={"collection_slug": "vibe"}).status_code == 422

    def test_cap_reached_409(self) -> None:
        client, _ = _research_client(spend=GLOBAL_MONTHLY_CAP)
        assert client.post("/api/research/runs", json={"collection_slug": "vibe"}).status_code == 409

    def test_spend_unavailable_503(self) -> None:
        client, _ = _research_client(spend_broken=True)
        assert client.post("/api/research/runs", json={"collection_slug": "vibe"}).status_code == 503

    def test_llm_unavailable_503_not_empty_500(self) -> None:
        client, _ = _research_client(
            starter=_FakeStarter(error=RuntimeError("OPENROUTER_API_KEY is not set")))
        resp = client.post("/api/research/runs", json={"collection_slug": "vibe"})
        assert resp.status_code == 503
        assert "OPENROUTER_API_KEY" in resp.json()["detail"]

    def test_viewer_cannot_start(self) -> None:
        client, _ = _research_client(role=ROLE_VIEWER)
        assert client.post("/api/research/runs", json={"collection_slug": "vibe"}).status_code == 403


class TestReadPaths:
    def _ports(self) -> _FakePorts:
        return _FakePorts([
            _snap("rsch_1", {"visited": ["inspiration_review", "style_synthesis"],
                             "collection_slug": "vibe"}),
            _snap("rsch_2", {"visited": ["inspiration_review"], "collection_slug": "vibe",
                             "board": {"board_version": 1}}, interrupted=True),
        ])

    def test_list_and_detail(self) -> None:
        client, _ = _research_client(ports=self._ports())
        items = client.get("/api/research/runs").json()["items"]
        assert {i["id"] for i in items} == {"rsch_1", "rsch_2"}
        detail = client.get("/api/research/runs/rsch_2").json()
        assert detail["status"] == "awaiting_approval"
        assert detail["board_version"] == 1
        assert len(detail["nodes"]) == len(RESEARCH_ORDER)

    def test_detail_404(self) -> None:
        client, _ = _research_client(ports=self._ports())
        assert client.get("/api/research/runs/rsch_9").status_code == 404
        assert client.get("/api/research/runs/run-1").status_code == 404

    def test_logs(self) -> None:
        rows = [{"run_id": "rsch_2", "node": "mood_board", "message": "rendering"}]
        client, _ = _research_client(ports=self._ports(), reader_rows=rows)
        body = client.get("/api/research/runs/rsch_2/logs").json()
        assert body["items"] == rows
        assert client.get("/api/research/runs/rsch_9/logs").status_code == 404
        assert client.get("/api/research/runs/rsch_2/logs?since=not-a-time").status_code == 422

    def test_viewer_reads(self) -> None:
        client, _ = _research_client(role=ROLE_VIEWER, ports=self._ports())
        assert client.get("/api/research/runs").status_code == 200
        assert client.get("/api/research/runs/rsch_1").status_code == 200


class TestBoardServe:
    def _client(self, tmp_path: Path, role: str = ROLE_ADMIN) -> TestClient:
        from api.app.collections_store import get_collections_store
        from api.app.routers import collections as collections_router

        store = _collections(tmp_path)
        assets = tmp_path / "collections" / "vibe.assets"
        assets.mkdir(parents=True, exist_ok=True)
        (assets / "board.png").write_bytes(PNG)
        (assets / "note.json").write_text("{}", encoding="utf-8")
        app = FastAPI()
        app.include_router(collections_router.router)
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", role)
        app.dependency_overrides[get_audit_writer] = lambda: _NoopAudit()
        app.dependency_overrides[get_collections_store] = lambda: store
        return TestClient(app, raise_server_exceptions=False)

    def test_serves_board_bytes(self, tmp_path: Path, monkeypatch) -> None:
        import pipeline.paths as paths

        monkeypatch.setenv(paths.COLLECTIONS_DIR_ENV, str(tmp_path / "collections"))
        resp = self._client(tmp_path).get("/api/collections/vibe/board/board.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == PNG

    def test_unknown_collection_404(self, tmp_path: Path, monkeypatch) -> None:
        import pipeline.paths as paths

        monkeypatch.setenv(paths.COLLECTIONS_DIR_ENV, str(tmp_path / "collections"))
        assert self._client(tmp_path).get("/api/collections/ghost/board/board.png").status_code == 404

    def test_missing_or_guarded_refs_404_or_422(self, tmp_path: Path, monkeypatch) -> None:
        import pipeline.paths as paths

        monkeypatch.setenv(paths.COLLECTIONS_DIR_ENV, str(tmp_path / "collections"))
        client = self._client(tmp_path)
        assert client.get("/api/collections/vibe/board/nope.png").status_code == 404
        assert client.get("/api/collections/vibe/board/note.json").status_code == 404
        assert client.get("/api/collections/vibe/board/../vibe.yaml").status_code in (404, 422)

    def test_viewer_reads(self, tmp_path: Path, monkeypatch) -> None:
        import pipeline.paths as paths

        monkeypatch.setenv(paths.COLLECTIONS_DIR_ENV, str(tmp_path / "collections"))
        assert self._client(tmp_path, ROLE_VIEWER).get("/api/collections/vibe/board/board.png").status_code == 200


class TestOfflineRoundTrip:
    """Real starter + shared MemorySaver: trigger → gate → decide → complete."""

    def _stack(self, tmp_path: Path, monkeypatch):
        import pipeline.paths as paths

        root = tmp_path / "collections"
        monkeypatch.setenv(paths.COLLECTIONS_DIR_ENV, str(root))
        # The synthesis node reads the locked repo through the env root —
        # seed it from the real file (same source production mounts).
        root.mkdir(parents=True, exist_ok=True)
        shutil.copy(
            Path(__file__).resolve().parent.parent.parent / "collections" / "styles.yaml",
            root / "styles.yaml",
        )
        store = _collections(tmp_path)
        insp = _seeded_inspiration(tmp_path, store)
        saver = MemorySaver()
        engine = _FakeEngine()
        logger = MemoryRunLogger()
        client = _StubClient(chat_content=json.dumps(GOOD_DIRECTIVES))
        shared = {"saver": saver, "engine": engine, "logger": logger, "client": client}
        starter = ResearchRunStarter(
            saver_factory=lambda: shared["saver"],
            llm_factory=lambda: shared["client"],
            engine_factory=lambda: shared["engine"],
            logger_factory=lambda _e, _r: shared["logger"],
            store_factory=lambda: store,
            inspiration_factory=lambda: insp,
        )
        ports = ResearchRunPorts(saver_factory=lambda: shared["saver"])
        runner = ResearchGraphRunner(
            saver_factory=lambda: shared["saver"],
            llm_factory=lambda: shared["client"],
            engine_factory=lambda: shared["engine"],
            logger_factory=lambda _e, _r: shared["logger"],
        )
        return starter, ports, runner, saver

    def _wait(self, ports: ResearchRunPorts, run_id: str, cond, timeout: float = 20.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                detail = research_run_detail(ports, run_id)
            except KeyError:
                time.sleep(0.05)
                continue
            if cond(detail):
                return detail
            time.sleep(0.05)
        raise AssertionError(f"research run {run_id} never settled")

    def _service(self, saver, runner):
        gates = CheckpointerGateSource(
            saver_factory=lambda: saver, graph_factory=build_collection_graph)
        return HitlService(gates=gates, index=_FakeIndex(), runner=runner, writer=_NoopAudit())

    def _paused(self, tmp_path, monkeypatch):
        starter, ports, runner, saver = self._stack(tmp_path, monkeypatch)
        result = starter.start(collection_slug="vibe", actor_user_id="u-9")
        run_id = result["run_id"]
        assert run_id.startswith(RESEARCH_RUN_PREFIX)
        paused = self._wait(ports, run_id, lambda d: d["status"] == "awaiting_approval")
        assert paused["board"] is not None
        assert paused["board_version"] == 1
        service = self._service(saver, runner)
        queue = service.list_queue()
        assert len(queue) == 1
        item = queue[0]
        assert item["node"] == "collection_gate"
        assert item["payload"]["draft"]["collection_id"] == "vibe"
        assert item["payload"]["board"]["board_version"] == 1
        assert isinstance(item["payload"]["diversity_flags"], list)
        assert item["entity_ref"]["id"] == "vibe"
        return ports, service, item, run_id

    def test_approve_completes_with_draft_and_board(self, tmp_path: Path, monkeypatch) -> None:
        ports, service, item, run_id = self._paused(tmp_path, monkeypatch)
        decided = service.decide(item["id"], action="approve", note="go",
                                 selection=None, actor_user_id="u-9")
        assert decided["resumed"] is True
        done = self._wait(ports, run_id, lambda d: d["status"] == "complete")
        assert done["draft_contract"]["collection_id"] == "vibe"
        assert done["gate_decision"]["approved"] is True
        # board bytes landed in the durable asset dir
        assert (tmp_path / "collections" / "vibe.assets" / "board.png").is_file()

    def test_reject_records_not_approved(self, tmp_path: Path, monkeypatch) -> None:
        ports, service, item, run_id = self._paused(tmp_path, monkeypatch)
        decided = service.decide(item["id"], action="reject", note="off-brief",
                                 selection=None, actor_user_id="u-9")
        assert decided["resumed"] is True
        done = self._wait(ports, run_id, lambda d: d["status"] == "complete")
        assert done["gate_decision"]["approved"] is False
        assert done["draft_contract"]["collection_id"] == "vibe"

    def test_edit_and_approve_merges_ceo_override(self, tmp_path: Path, monkeypatch) -> None:
        ports, service, item, run_id = self._paused(tmp_path, monkeypatch)
        decided = service.decide(item["id"], action="approve", note="with edits",
                                 selection={"contract": {"theme": "CEO Theme"}},
                                 actor_user_id="u-9")
        assert decided["resumed"] is True
        done = self._wait(ports, run_id, lambda d: d["status"] == "complete")
        assert done["gate_decision"]["approved"] is True
        assert done["gate_decision"]["edited_contract"]["theme"] == "CEO Theme"
        assert done["gate_decision"]["edited_contract"]["collection_id"] == "vibe"

    def test_list_only_research(self, tmp_path: Path, monkeypatch) -> None:
        starter, ports, _, _ = self._stack(tmp_path, monkeypatch)
        result = starter.start(collection_slug="vibe", actor_user_id="u-9")
        self._wait(ports, result["run_id"], lambda d: d["status"] == "awaiting_approval")
        rows = list_research_runs(ports)
        assert [r["id"] for r in rows] == [result["run_id"]]
        assert rows[0]["collection_slug"] == "vibe"


class TestQueueNamespaces:
    """Gate scans stay in their thread namespace (adversarial finding).

    Without the filter a research gate decided from the item queue would
    resume with the item graph — the wrong runtime for a research thread.
    """

    def test_item_wiring_excludes_research(self) -> None:
        from api.app.hitl import get_gate_source

        source = get_gate_source()
        assert source._thread_filter is not None
        assert source._thread_filter("rsch_abc") is False
        assert source._thread_filter("run-1") is True

    def test_scans_route_to_their_graph(self, tmp_path: Path, monkeypatch) -> None:
        from pipeline.graph import build_graph

        from api.app.hitl import CheckpointerGateSource

        starter, ports, _, saver = TestOfflineRoundTrip()._stack(tmp_path, monkeypatch)
        result = starter.start(collection_slug="vibe", actor_user_id="u-9")
        deadline = time.time() + 20.0
        while time.time() < deadline:
            try:
                detail = research_run_detail(ports, result["run_id"])
            except KeyError:
                time.sleep(0.05)
                continue
            if detail["status"] == "awaiting_approval":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("research run never paused")

        item_source = CheckpointerGateSource(
            saver_factory=lambda: saver,
            graph_factory=build_graph,
            thread_filter=lambda tid: not tid.startswith(RESEARCH_RUN_PREFIX))
        research_source = CheckpointerGateSource(
            saver_factory=lambda: saver,
            graph_factory=build_collection_graph,
            thread_filter=lambda tid: tid.startswith(RESEARCH_RUN_PREFIX))
        assert item_source.list_interrupts() == []
        found = research_source.list_interrupts()
        assert [(i.run_id, i.node) for i in found] == [(result["run_id"], "collection_gate")]
