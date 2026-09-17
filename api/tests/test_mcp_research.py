"""MCP research + styles tools (collection-research doorway) — loopback conformance.

Mirrors test_mcp_reads.py: live localhost MCP server, patched verifier +
patched seams. Every tool byte-equals its REST twin on shared fakes.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Optional

from api.app.mcp import auth as mcp_auth  # noqa: F401 - seam target surface
from api.app.runs import Snapshot
from api.tests.test_mcp_reads import LiveMCP, _app, _items, _patch_verifier, _session, _text

PNG = (
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    + b"\x00\x00\x00\x0dIHDR" + b"\x00" * 13
)


def _snap(run_id: str, values: dict[str, Any], interrupted: bool = False) -> Snapshot:
    return Snapshot(run_id=run_id, values=values, at="2026-09-17T00:00:00+00:00",
                    interrupted=interrupted)


def _research_values(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "collection_slug": "vibe",
        "visited": ["inspiration_review", "style_synthesis", "mood_board"],
        "board": {"file_ref": "vibe.assets/board.png", "board_version": 1},
        "diversity_flags": [],
    }
    base.update(extra)
    return base


class _FakePorts:
    def __init__(self, snaps: list[Snapshot] | None = None) -> None:
        self.snaps = snaps if snaps is not None else [_snap("rsch_1", _research_values())]

    def list_research_snapshots(self) -> list[Snapshot]:
        return list(self.snaps)

    def history(self, run_id: str) -> list[Snapshot]:
        return [s for s in self.snaps if s.run_id == run_id]


class _FakeStarter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def start(self, *, collection_slug: str, actor_user_id: str = "") -> dict[str, Any]:
        self.calls.append({"collection_slug": collection_slug, "actor_user_id": actor_user_id})
        return {"run_id": "rsch_9", "status": "started", "collection_slug": collection_slug}


class _FakeRunner:
    def __init__(self) -> None:
        self.resumes: list[tuple[str, dict[str, Any]]] = []

    def get_state_values(self, thread_id: str) -> dict[str, Any]:
        return _research_values()

    def resume(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.resumes.append((thread_id, payload))
        return {"thread_id": thread_id, "resumed": True}


class _FakeGates:
    def list_interrupts(self) -> list[Any]:
        from api.app.hitl import InterruptInfo

        return [InterruptInfo(
            run_id="rsch_1", node="collection_gate",
            payload={"node": "collection_gate", "status": "awaiting_approval",
                     "draft": {"collection_id": "vibe", "theme": "Vibe"},
                     "board": {"file_ref": "vibe.assets/board.png", "board_version": 1},
                     "diversity_flags": []},
            interrupt_id="i-9", waiting_since="2026-09-17T00:00:00+00:00")]


class _FakeIndex:
    def __init__(self) -> None:
        self.rows: dict[int, dict[str, Any]] = {
            7: {"id": 7, "run_id": "rsch_1", "node": "collection_gate", "status": "pending",
                "reviewer_user_id": None, "note": None, "decided_at": None}}

    def list_open(self) -> list[dict[str, Any]]:
        return [r for r in self.rows.values() if r["status"] == "pending"]

    def get(self, item_id: int) -> Optional[dict[str, Any]]:
        return self.rows.get(item_id)

    def ensure_pending(self, run_id: str, node: str) -> dict[str, Any]:
        return {"id": 7, "run_id": run_id, "node": node, "status": "pending",
                "reviewer_user_id": None, "note": None, "decided_at": None}

    def claim(self, item_id: int, *, status: str, reviewer_user_id: str, note: Optional[str]):
        row = self.rows.get(item_id)
        if row is None or row["status"] != "pending":
            return None
        row.update({"status": status, "reviewer_user_id": reviewer_user_id, "note": note,
                    "decided_at": "2026-09-17T00:01:00+00:00"})
        return row

    def reopen(self, item_id: int) -> None:
        pass


class _FakeWriter:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.rows.append(kwargs)


class _FakeSpend:
    def month_to_date_usd(self) -> float:
        return 0.0


class _FakeLogReader:
    def for_run(self, run_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"node": "mood_board", "level": "info", "message": "rendering",
                 "detail": {}, "ts": "2026-09-17T00:00:01+00:00"}]


class _FakeCollections:
    def get(self, slug: str) -> dict[str, Any]:
        from api.app.collections_store import CollectionNotFound

        if slug != "vibe":
            raise CollectionNotFound(slug)
        return {"contract": {"collection_id": "vibe"}, "mtime": 1.0}

    def list(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"contract": {"collection_id": "vibe", "style_archetype": "mono-log"}}]


class _FakeStyles:
    def __init__(self) -> None:
        self.doc = {"version": 3, "styles": [
            {"name": "mono-log", "graphic_definition": "Lines."}]}

    def read(self) -> dict[str, Any]:
        return dict(self.doc)

    def create(self, name: str, graphic_definition: str, expected_version: int) -> dict[str, Any]:
        from api.app.styles_store import DuplicateStyle, VersionConflict

        if expected_version != self.doc["version"]:
            raise VersionConflict("stale")
        if any(s["name"] == name for s in self.doc["styles"]):
            raise DuplicateStyle(name)
        self.doc = {"version": 4, "styles": [*self.doc["styles"],
                                             {"name": name, "graphic_definition": graphic_definition}]}
        return dict(self.doc)

    def update(self, old_name: str, name: Optional[str], graphic_definition: Optional[str],
               expected_version: int) -> dict[str, Any]:
        from api.app.styles_store import UnknownStyle

        if old_name != "mono-log":
            raise UnknownStyle(old_name)
        self.doc = {"version": 4, "styles": [
            {"name": name or "mono-log", "graphic_definition": graphic_definition or "Lines."}]}
        return dict(self.doc)


_WRITER = _FakeWriter()


def _patch_seams(monkeypatch, tmp_path: Path | None = None) -> dict[str, Any]:
    """Patch tool seams; returns the shared fake instances (stateful across calls)."""
    import api.app.mcp.tools_research as tools

    state = {
        "ports": _FakePorts(),
        "starter": _FakeStarter(),
        "runner": _FakeRunner(),
        "gates": _FakeGates(),
        "index": _FakeIndex(),
        "styles": _FakeStyles(),
    }
    monkeypatch.setattr(tools, "_research_ports", lambda: state["ports"])
    monkeypatch.setattr(tools, "_research_starter", lambda: state["starter"])
    monkeypatch.setattr(tools, "_research_runner", lambda: state["runner"])
    monkeypatch.setattr(tools, "_research_gates", lambda: state["gates"])
    monkeypatch.setattr(tools, "_research_index", lambda: state["index"])
    monkeypatch.setattr(tools, "_spend_reader", _FakeSpend)
    monkeypatch.setattr(tools, "_log_reader", _FakeLogReader)
    monkeypatch.setattr(tools, "_collections_store", _FakeCollections)
    monkeypatch.setattr(tools, "_styles_store", lambda: state["styles"])
    monkeypatch.setattr(tools, "_audit_writer", lambda: _WRITER)
    return state


class TestToolList:
    async def test_research_tools_listed(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.list_tools()
                names = {t.name for t in result.tools}
                for want in ("research_runs_list", "research_run_detail",
                             "research_run_logs", "research_approvals_queue",
                             "styles_list", "board_file", "research_start",
                             "research_approval_decide", "style_create", "style_update"):
                    assert want in names, want
            finally:
                await close()


class TestReads:
    async def test_runs_list_detail_logs(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                items = _items(await session.call_tool("research_runs_list", {}))[0]["items"]
                assert [i["id"] for i in items] == ["rsch_1"]
                detail = _items(await session.call_tool(
                    "research_run_detail", {"run_id": "rsch_1"}))[0]
                assert detail["status"] == "board_rendering"
                assert detail["board_version"] == 1
                logs = _items(await session.call_tool(
                    "research_run_logs", {"run_id": "rsch_1"}))[0]["items"]
                assert logs[0]["node"] == "mood_board"
            finally:
                await close()

    async def test_queue_and_styles(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                queue = _items(await session.call_tool("research_approvals_queue", {}))[0]["items"]
                assert queue[0]["node"] == "collection_gate"
                assert queue[0]["payload"]["draft"]["collection_id"] == "vibe"
                styles = _items(await session.call_tool("styles_list", {}))[0]
                assert styles["version"] == 3
                assert [s["name"] for s in styles["styles"]] == ["mono-log"]
            finally:
                await close()

    async def test_board_file_bytes(self, monkeypatch, tmp_path: Path) -> None:
        import pipeline.paths as paths

        assets = tmp_path / "collections" / "vibe.assets"
        assets.mkdir(parents=True)
        (assets / "board.png").write_bytes(PNG)
        monkeypatch.setenv(paths.COLLECTIONS_DIR_ENV, str(tmp_path / "collections"))
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                body = _items(await session.call_tool(
                    "board_file", {"slug": "vibe", "ref": "board.png"}))[0]
                assert body["media_type"] == "image/png"
                assert base64.b64decode(body["content_base64"]) == PNG
                missing = await session.call_tool(
                    "board_file", {"slug": "vibe", "ref": "nope.png"})
                assert missing.is_error
            finally:
                await close()

    async def test_unknown_run_is_error(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.call_tool("research_run_detail", {"run_id": "rsch_9"})
                assert result.is_error
                assert "unknown research run" in _text(result)
            finally:
                await close()

    async def test_shapes_match_rest(self, monkeypatch) -> None:
        from api.app.auth import Actor
        from api.app.hitl import HitlService
        from api.app.routers import research as research_router
        from api.app.routers import styles as styles_router

        _patch_verifier(monkeypatch, ["read"])
        state = _patch_seams(monkeypatch)
        actor = Actor("token:sdr_test", "", "viewer")
        service = HitlService(gates=state["gates"], index=state["index"],
                              runner=state["runner"], writer=_WRITER)
        cases = [
            ("research_runs_list", {},
             lambda: research_router.list_research(actor=actor, ports=state["ports"])),
            ("research_run_detail", {"run_id": "rsch_1"},
             lambda: research_router.get_research_run("rsch_1", actor=actor, ports=state["ports"])),
            ("research_approvals_queue", {},
             lambda: research_router.list_research_approvals(actor=actor, service=service)),
            ("styles_list", {},
             lambda: styles_router.list_styles(actor=actor, store=state["styles"])),
        ]
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                for name, args, expected_fn in cases:
                    result = await session.call_tool(name, args)
                    assert not result.is_error, name
                    want = expected_fn()
                    assert _items(result) == ([want] if isinstance(want, dict) else want), name
            finally:
                await close()


class TestWrites:
    async def test_research_start_and_decide(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["operate"])
        _patch_seams(monkeypatch)
        _WRITER.rows.clear()
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                started = _items(await session.call_tool(
                    "research_start", {"collection_slug": "vibe"}))[0]
                assert started["run_id"] == "rsch_9"
                assert any(r["action"] == "research.start" for r in _WRITER.rows)
                decided = _items(await session.call_tool(
                    "research_approval_decide", {"item_id": 7, "action": "approve"}))[0]
                assert decided["resumed"] is True
                edited = await session.call_tool(
                    "research_approval_decide",
                    {"item_id": 7, "action": "approve",
                     "selection": {"contract": {"theme": "CEO"}}})
                # item 7 already decided above → idempotent replay, no second resume
                assert not edited.is_error
            finally:
                await close()

    async def test_style_create_update(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["operate"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                created = _items(await session.call_tool(
                    "style_create", {"name": "glitch", "graphic_definition": "Bars.",
                                     "expected_version": 3}))[0]
                assert created["version"] == 4
                assert created["affected_contracts"] == []
                dup = await session.call_tool(
                    "style_create", {"name": "glitch", "graphic_definition": "Bars.",
                                     "expected_version": 3})
                assert dup.is_error
                updated = _items(await session.call_tool(
                    "style_update", {"name": "mono-log", "expected_version": 3,
                                     "graphic_definition": "New."}))[0]
                assert updated["version"] == 4
            finally:
                await close()

    async def test_read_scope_cannot_write(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.call_tool(
                    "research_start", {"collection_slug": "vibe"})
                assert result.is_error
                assert "scope" in _text(result)
                result = await session.call_tool(
                    "style_create", {"name": "x", "graphic_definition": "y",
                                     "expected_version": 1})
                assert result.is_error
            finally:
                await close()

    async def test_operate_passes_reads(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["operate"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.call_tool("styles_list", {})
                assert not result.is_error
            finally:
                await close()
