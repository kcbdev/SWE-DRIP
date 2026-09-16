"""MCP read doorway conformance (PBI-044, spec C2/C4/C6) — offline.

A real SDK client speaks to a live localhost uvicorn server (same pattern as
test_stream.py's LiveServer): handshake, auth matrix, tool listing, tool calls
against fakes, and error mapping. No network beyond loopback, no database.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Optional

import httpx
import pytest
from fastapi import FastAPI

from api.app.mcp import auth as mcp_auth
from api.app.mcp.server import SERVER_NAME, build_server
from api.app.runs import RunService, Snapshot
from pipeline.routing import NODE_ORDER


# ---------------------------------------------------------------------------
# Fakes (mirror test_runs.py / test_designs.py shapes)
# ---------------------------------------------------------------------------

def _values(visited, **extra) -> dict[str, Any]:
    base: dict[str, Any] = {"design_id": "d-1", "collection_id": "vibe-coding",
                            "visited": list(visited)}
    base.update(extra)
    return base


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
    def replay(self, run_id: str, node: str, recorded: Any) -> dict[str, Any]:
        raise AssertionError("no replay on the read path")


class FakeWriter:
    def record(self, **kwargs: Any) -> None:
        pass


def _service() -> RunService:
    snaps = [Snapshot("run-1", _values(["trend_research"]), "2026-09-16T00:00:00+00:00")]
    return RunService(
        scanner=FakeScanner(snaps),
        history=FakeHistory({"run-1": snaps}),
        executor=FakeExecutor(),
        writer=FakeWriter(),
    )


class FakeLogReader:
    def for_run(self, run_id: str, *, node=None, level=None, since=None,
                limit: int = 500) -> list[dict[str, Any]]:
        return [{"node": "trend_research", "level": "info", "message": "clustering",
                 "detail": {}, "ts": "2026-09-16T00:00:01+00:00"}]


class FakeHitl:
    def list_queue(self) -> list[dict[str, Any]]:
        return [{"id": 1, "run_id": "run-1", "node": "contract_approval",
                 "status": "pending"}]


class FakeAuditReader:
    def list_entries(self, filters: Any) -> list[dict[str, Any]]:
        return [{"id": 1, "actor_user_id": "u-9", "action": "run.start",
                 "entity_type": "run", "entity_id": "run-1",
                 "before_json": None, "after_json": {}}]


class FakeRunner:
    def get_state_values(self, thread_id: str) -> dict[str, Any]:
        return _values(["trend_research"],
                       aesthetic_qc={"result": "pass",
                                     "scores": {"style_cohesion": 88, "focal_point": 92,
                                                "placement_fit": 85, "contrast": 90},
                                     "failing": [], "attempts": 1, "model_used": "m",
                                     "rubric_version": 1,
                                     "prompt_version": "e01d513a5ce4",
                                     "prompt_key": "qc_rubric"},
                       render_result={"file_url": "runs/d-1/render.png"})


class FakeIndex:
    def list_for_run(self, run_id: str) -> list[dict[str, Any]]:
        return []


class _FakeStore:
    def get(self, slug: str) -> dict[str, Any]:
        from api.app.collections_store import CollectionNotFound

        if slug != "vibe":
            raise CollectionNotFound(slug)
        return {"contract": {"collection_id": "vibe", "theme": "Vibe"},
                "status": "active"}


def _fake_store() -> Any:
    return _FakeStore()


# ---------------------------------------------------------------------------
# Live localhost server (uvicorn in a thread, ephemeral port)
# ---------------------------------------------------------------------------

class LiveMCP:
    def __init__(self, app: FastAPI) -> None:
        import uvicorn

        self._config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
        self._server = uvicorn.Server(self._config)

    async def __aenter__(self) -> str:
        thread = threading.Thread(target=self._server.run, daemon=True)
        thread.start()
        while not self._server.started:
            await asyncio.sleep(0.02)
        port = self._server.servers[0].sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}/mcp/"

    async def __aexit__(self, *args: object) -> None:
        self._server.should_exit = True


def _app() -> FastAPI:
    from api.app.mcp.server import mount_operator_mcp

    app = FastAPI()
    mount_operator_mcp(app)
    return app


class _AuthState:
    """Mutable verifier outcome: scopes list, or None once 'revoked'."""

    def __init__(self, scopes: list[str] | None) -> None:
        self.scopes = scopes

    async def verify(self, token: str):
        from mcp.server.auth.provider import AccessToken

        if self.scopes is None:
            return None
        return AccessToken(token="token:sdr_test", client_id="token:sdr_test",
                           scopes=list(self.scopes), subject="u-9")


def _patch_verifier(monkeypatch, scopes: list[str] | None) -> _AuthState:
    """Fake the store check; mutate the returned state to revoke mid-test."""
    state = _AuthState(scopes)

    async def fake_verify(self, token: str):
        return await state.verify(token)

    monkeypatch.setattr(mcp_auth.OperatorTokenVerifier, "verify_token", fake_verify)
    return state


def _patch_seams(monkeypatch) -> None:
    import api.app.mcp.tools_reads as reads

    monkeypatch.setattr(reads, "_run_service", _service)
    monkeypatch.setattr(reads, "_log_reader", FakeLogReader)
    monkeypatch.setattr(reads, "_hitl_service", FakeHitl)
    monkeypatch.setattr(reads, "_audit_reader", FakeAuditReader)
    monkeypatch.setattr(reads, "_graph_runner", FakeRunner)
    monkeypatch.setattr(reads, "_approval_index", FakeIndex)
    monkeypatch.setattr(reads, "_collections_store", _fake_store)
    from api.app import model_catalog

    model_catalog.reset_cache()
    model_catalog._install_test_cache([{
        "id": "google/gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite",
        "context_length": 1000000,
        "pricing": {"prompt": "0.0000003", "completion": "0.0000025"},
        "architecture": {"input_modalities": ["text", "image"]},
    }])


async def _session(url: str, token: Optional[str]):
    """Open an SDK client session (caller closes). Returns (session, close)."""
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    client = httpx.AsyncClient(headers=headers, timeout=30.0)
    transport = streamable_http_client(url, http_client=client)
    read, write, *_ = await transport.__aenter__()
    session = ClientSession(read, write)
    await session.__aenter__()
    await session.initialize()

    async def close() -> None:
        await session.__aexit__(None, None, None)
        await transport.__aexit__(None, None, None)
        await client.aclose()

    return session, close


def _items(result: Any) -> list[Any]:
    """Parsed content items, always a list (multi-content list results fan out)."""
    return [json.loads(b.text) for b in (result.content or []) if hasattr(b, "text")]


def _text(result: Any) -> str:
    return "".join(b.text for b in (result.content or []) if hasattr(b, "text"))


# ---------------------------------------------------------------------------
# Transport auth
# ---------------------------------------------------------------------------

class TestMountAuth:
    async def test_missing_token_401(self) -> None:
        async with LiveMCP(_app()) as url:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={"jsonrpc": "2.0", "id": 1,
                                                    "method": "tools/list", "params": {}})
                assert resp.status_code == 401

    async def test_unknown_token_401(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, None)
        async with LiveMCP(_app()) as url:
            async with httpx.AsyncClient(
                    headers={"Authorization": "Bearer sdr_nope"}, timeout=10.0) as client:
                resp = await client.post(url, json={"jsonrpc": "2.0", "id": 1,
                                                    "method": "tools/list", "params": {}})
                assert resp.status_code == 401

    async def test_revoked_token_401_on_next_request(self, monkeypatch) -> None:
        state = _patch_verifier(monkeypatch, ["read"])
        async with LiveMCP(_app()) as url:
            async with httpx.AsyncClient(
                    headers={"Authorization": "Bearer sdr_test"}, timeout=10.0) as client:
                body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
                assert (await client.post(url, json=body)).status_code != 401
                state.scopes = None  # revocation bites on the next request
                assert (await client.post(url, json=body)).status_code == 401

    async def test_cookie_without_bearer_401(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        async with LiveMCP(_app()) as url:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url, json={"jsonrpc": "2.0", "id": 1,
                               "method": "tools/list", "params": {}},
                    cookies={"better-auth.session_token": "valid-looking"})
                assert resp.status_code == 401

    def test_mounted_in_main_app(self) -> None:
        from api.app.main import app as main_app

        paths = [getattr(r, "path", "") for r in main_app.routes]
        assert "/mcp" in paths


# ---------------------------------------------------------------------------
# Tool listing + read calls through a real client
# ---------------------------------------------------------------------------

EXPECTED_TOOLS = {
    "runs_list", "run_detail", "run_logs", "approvals_queue", "agents_roster",
    "models_search", "prompt_meta", "collection_get", "audit_query",
    "calibration_get", "graph_inspect",
    "run_start", "approval_decide", "agent_config", "run_replay",
}


class TestReadTools:
    async def test_lists_all_read_tools(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                tools = await session.list_tools()
                assert {t.name for t in tools.tools} == EXPECTED_TOOLS
                assert session.server_info and SERVER_NAME in str(session.server_info)
            finally:
                await close()

    async def test_runs_list_shape(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.call_tool("runs_list", {})
                assert not result.is_error
                body = json.loads(_text(result))
                assert [i["id"] for i in body["items"]] == ["run-1"]
            finally:
                await close()

    async def test_run_detail_and_logs(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                detail = _items(await session.call_tool(
                    "run_detail", {"run_id": "run-1"}))[0]
                assert detail["id"] == "run-1"
                assert len(detail["nodes"]) == 11
                logs = _items(await session.call_tool(
                    "run_logs", {"run_id": "run-1", "level": "info"}))[0]
                assert logs["items"][0]["message"] == "clustering"
            finally:
                await close()

    async def test_agents_roster_prompt_meta_queue_audit(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                roster = _items(await session.call_tool("agents_roster", {}))
                assert len(roster) == 11 and all("model_source" in a for a in roster)
                meta = _items(await session.call_tool(
                    "prompt_meta", {"node": "aesthetic_qc"}))[0]
                assert meta["prompt_key"] == "qc_rubric"
                queue = _items(await session.call_tool("approvals_queue", {}))[0]
                assert queue["items"][0]["node"] == "contract_approval"
                audit = _items(await session.call_tool(
                    "audit_query", {"action": "run.start"}))
                assert audit[0]["entity_id"] == "run-1"
                models = _items(await session.call_tool(
                    "models_search", {"q": "gemini"}))[0]
                assert models["models"][0]["id"] == "google/gemini-3.5-flash-lite"
            finally:
                await close()

    async def test_graph_inspect_matches_locked_order(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                graph = _items(await session.call_tool("graph_inspect", {}))[0]
                assert graph["node_order"] == list(NODE_ORDER)
                assert len(graph["edges"]["linear"]) == 10
                assert graph["edges"]["conditional"]["aesthetic_qc"] == [
                    "art_render", "technical_qc"]
                assert set(graph["nodes"]) == set(NODE_ORDER)
            finally:
                await close()

    async def test_unknown_run_is_error_not_traceback(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.call_tool("run_detail", {"run_id": "ghost"})
                assert result.is_error
                assert "unknown run" in _text(result)
                assert "Traceback" not in _text(result)
            finally:
                await close()

    async def test_scope_is_checked_per_tool(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, [])  # valid token, no scopes
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.call_tool("runs_list", {})
                assert result.is_error
                assert "scope" in _text(result)
            finally:
                await close()

    async def test_operate_token_passes_reads(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["operate"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.call_tool("runs_list", {})
                assert not result.is_error
            finally:
                await close()

    async def test_tool_shape_equals_rest_shape(self, monkeypatch) -> None:
        """Parity by byte, not by promise: same fakes through both doorways."""
        from api.app.auth import Actor
        from api.app.routers import runs as runs_router

        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        expected = runs_router.list_runs(
            actor=Actor("token:sdr_test", "", "viewer"), service=_service(),
            collection=None, status_filter=None, date=None,
        )
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                body = _items(await session.call_tool("runs_list", {}))[0]
                assert body == expected
            finally:
                await close()

    async def test_all_tools_match_rest_shapes(self, monkeypatch) -> None:
        """Every read tool byte-equals its REST twin on shared fakes."""
        from api.app.auth import Actor
        from api.app.routers import agents as agents_router
        from api.app.routers import approvals as approvals_router
        from api.app.routers import audit as audit_router
        from api.app.routers import collections as collections_router
        from api.app.routers import designs as designs_router
        from api.app.routers import runs as runs_router

        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        actor = Actor("token:sdr_test", "", "viewer")
        service, reader = _service(), FakeLogReader()
        cases = [
            ("run_detail", {"run_id": "run-1"},
             lambda: runs_router.get_run("run-1", actor=actor, service=service)),
            ("run_logs", {"run_id": "run-1"},
             lambda: runs_router.get_run_logs("run-1", actor=actor, service=service,
                                              reader=reader, node=None, level=None,
                                              since=None, limit=500)),
            ("approvals_queue", {},
             lambda: approvals_router.list_approvals(actor=actor, service=FakeHitl())),
            ("agents_roster", {},
             lambda: agents_router.list_agents(actor=actor)),
            ("models_search", {"q": "gemini"},
             lambda: agents_router.list_catalog_models(q="gemini", actor=actor)),
            ("prompt_meta", {"node": "placement"},
             lambda: agents_router.get_agent_prompt("placement", actor=actor)),
            ("collection_get", {"slug": "vibe"},
             lambda: collections_router.get_collection("vibe", actor=actor,
                                                       store=_fake_store())),
            ("audit_query", {"action": "run.start"},
             lambda: audit_router.list_audit(actor=actor, reader=FakeAuditReader(),
                                             filter_actor=None, action="run.start",
                                             entity_type=None, entity_id=None,
                                             limit=500)),
            ("calibration_get", {"design_id": "run-1"},
             lambda: designs_router.get_design_calibration(
                 "run-1", actor=actor, runner=FakeRunner(), index=FakeIndex())),
        ]
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                for name, args, expected_fn in cases:
                    result = await session.call_tool(name, args)
                    assert not result.is_error, name
                    # Transport fans list results across contents; dicts stay whole.
                    want = expected_fn()
                    assert _items(result) == ([want] if isinstance(want, dict) else want), name
            finally:
                await close()

    async def test_collection_unknown_is_error(self, monkeypatch) -> None:
        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.call_tool("collection_get", {"slug": "ghost"})
                assert result.is_error
                assert "unknown collection" in _text(result)
            finally:
                await close()

    async def test_graph_reports_live_store_overrides(self, monkeypatch) -> None:
        from api.app.settings_store import reset_cache, set_node_config_override

        _patch_verifier(monkeypatch, ["read"])
        _patch_seams(monkeypatch)
        reset_cache()
        try:
            set_node_config_override("trend_research", {"model": "m"})
            async with LiveMCP(_app()) as url:
                session, close = await _session(url, "sdr_test")
                try:
                    graph = _items(await session.call_tool("graph_inspect", {}))[0]
                    assert graph["nodes"]["trend_research"]["store_overridden"] == ["model"]
                    assert graph["nodes"]["placement"]["store_overridden"] == []
                finally:
                    await close()
        finally:
            reset_cache()
