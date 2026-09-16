"""MCP write doorway conformance (PBI-045, spec C3) — offline.

Real SDK client over live loopback (same harness as test_mcp_reads): scope
matrix, validation/audit parity with the REST twins on shared fakes, and
rejection wording. No network beyond loopback, no database, no graph run.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest

from api.app.mcp import auth as mcp_auth
from api.tests.test_mcp_reads import (  # same harness, same fakes philosophy
    FakeHitl,
    FakeLogReader,
    LiveMCP,
    _app,
    _items,
    _patch_seams,
    _patch_verifier,
    _service,
    _session,
    _text,
)


def _patch_writes(monkeypatch, starter, spend, audit) -> None:
    import api.app.mcp.tools_writes as writes

    monkeypatch.setattr(writes, "_run_starter", lambda: starter)
    monkeypatch.setattr(writes, "_spend_reader", lambda: spend)
    monkeypatch.setattr(writes, "_audit_writer", lambda: audit)
    monkeypatch.setattr(writes, "_hitl_service", lambda: FakeHitlService())
    monkeypatch.setattr(writes, "_run_service", _service)


class FakeStarter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def start(self, *, collection_id: str, design_id=None, briefs=None,
              design_type=None) -> dict[str, Any]:
        self.calls.append({"collection_id": collection_id, "design_id": design_id,
                           "briefs": briefs, "design_type": design_type})
        return {"run_id": "run-abc", "status": "running",
                "collection_id": collection_id, "design_id": design_id or "run-abc",
                "hitl": {"contract_approval": True}}


class FakeSpend:
    def __init__(self, amount: float = 0.0) -> None:
        self.amount = amount

    def month_to_date_usd(self) -> float:
        return self.amount


class BrokenSpend:
    def month_to_date_usd(self) -> float:
        from api.app.runs import SpendUnavailable

        raise SpendUnavailable("no relation")


class FakeAudit:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.rows.append(kwargs)


class FakeHitlService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def list_queue(self) -> list[dict[str, Any]]:
        return []

    def decide(self, item_id: int, *, action: str, note: Optional[str],
               selection: Optional[dict[str, Any]], actor_user_id: str) -> dict[str, Any]:
        if item_id != 7:
            raise KeyError(f"unknown approval {item_id}")
        self.calls.append({"item_id": item_id, "action": action, "actor": actor_user_id})
        return {"id": item_id, "status": action + "d", "resumed": True}


BRIEFS = [{"id": "b1", "subject": "Vibe", "text": "tee", "style": "mono-log",
           "engagement": 35, "novelty": 20, "specificity": 15}]


def _setup(monkeypatch, scopes=("operate",), spend: float = 0.0):
    _patch_verifier(monkeypatch, list(scopes))
    _patch_seams(monkeypatch)
    starter, audit = FakeStarter(), FakeAudit()
    _patch_writes(monkeypatch, starter, FakeSpend(spend), audit)
    from api.app.settings_store import reset_cache

    reset_cache()
    return starter, audit


class TestWriteScope:
    @pytest.mark.parametrize("tool,args", [
        ("run_start", {"collection_id": "c", "briefs": BRIEFS}),
        ("approval_decide", {"item_id": 7, "action": "approve"}),
        ("agent_config", {"node": "shelf", "cost_impact_note": "x", "cap_usd": 60.0}),
        ("run_replay", {"run_id": "run-1", "node": "trend_research"}),
    ])
    async def test_read_token_403_on_writes(self, monkeypatch, tool, args) -> None:
        _setup(monkeypatch, ["read"])
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.call_tool(tool, args)
                assert result.is_error
                assert "operate" in _text(result)
            finally:
                await close()


class TestRunStart:
    async def test_start_returns_run_and_audits(self, monkeypatch) -> None:
        starter, audit = _setup(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                body = _items(await session.call_tool(
                    "run_start", {"collection_id": "vibe", "briefs": BRIEFS}))[0]
                assert body["run_id"] == "run-abc" and body["status"] == "running"
                assert starter.calls[0]["collection_id"] == "vibe"
                assert audit.rows and audit.rows[0]["action"] == "run.start"
                assert audit.rows[0]["actor_user_id"] == "token:sdr_test"
            finally:
                await close()

    async def test_start_rejections_match_rest(self, monkeypatch) -> None:
        _setup(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                empty = await session.call_tool(
                    "run_start", {"collection_id": "vibe", "briefs": []})
                assert empty.is_error and "brief" in _text(empty)
                bad_type = await session.call_tool(
                    "run_start", {"collection_id": "vibe", "briefs": BRIEFS,
                                  "design_type": "nope"})
                assert bad_type.is_error and "design_type" in _text(bad_type)
            finally:
                await close()

    async def test_start_cost_guard_409(self, monkeypatch) -> None:
        from api.app.agents import GLOBAL_MONTHLY_CAP

        _setup(monkeypatch, spend=GLOBAL_MONTHLY_CAP)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.call_tool(
                    "run_start", {"collection_id": "vibe", "briefs": BRIEFS})
                assert result.is_error and "budget cap" in _text(result)
            finally:
                await close()


class TestApprovalDecide:
    async def test_decide_and_unknown(self, monkeypatch) -> None:
        starter, audit = _setup(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                body = _items(await session.call_tool(
                    "approval_decide", {"item_id": 7, "action": "approve",
                                        "note": "lgtm"}))[0]
                assert body["resumed"] is True
                missing = await session.call_tool(
                    "approval_decide", {"item_id": 99, "action": "approve"})
                assert missing.is_error and "unknown approval" in _text(missing)
                bad_action = await session.call_tool(
                    "approval_decide", {"item_id": 7, "action": "explode"})
                assert bad_action.is_error
            finally:
                await close()


class TestAgentConfig:
    async def test_cap_and_model_accepted_and_audited(self, monkeypatch) -> None:
        starter, audit = _setup(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                body = _items(await session.call_tool("agent_config", {
                    "node": "trend_research", "cost_impact_note": "mcp test",
                    "cap_usd": 60.0,
                    "model": "google/gemini-3.5-flash-lite"}))[0]
                assert body["cap_usd"] == 60.0
                assert body["model"] == "google/gemini-3.5-flash-lite"
                actions = {r["action"] for r in audit.rows}
                assert "agents.budget_cap.update" in actions
                assert "agents.model.update" in actions
            finally:
                await close()

    async def test_dead_model_rejected_with_suggestions(self, monkeypatch) -> None:
        _setup(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                result = await session.call_tool("agent_config", {
                    "node": "trend_research", "cost_impact_note": "x",
                    "model": "google/gemini-2.0-flash-001"})
                assert result.is_error
                text = _text(result)
                assert "Unknown model" in text and "gemini-3.5-flash-lite" in text
            finally:
                await close()

    async def test_note_prompt_scope_and_clear(self, monkeypatch) -> None:
        _setup(monkeypatch)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                no_note = await session.call_tool(
                    "agent_config", {"node": "shelf", "cost_impact_note": "  ",
                                     "cap_usd": 60.0})
                assert no_note.is_error and "cost_impact_note" in _text(no_note)
                bad_prompt = await session.call_tool(
                    "agent_config", {"node": "placement", "cost_impact_note": "x",
                                     "prompt_override": "whatever"})
                assert bad_prompt.is_error and "prompt" in _text(bad_prompt)
                conflict = await session.call_tool(
                    "agent_config", {"node": "shelf", "cost_impact_note": "x",
                                     "enabled": False, "clear": ["enabled"]})
                assert conflict.is_error and "both set and cleared" in _text(conflict)
                cleared = _items(await session.call_tool(
                    "agent_config", {"node": "shelf", "cost_impact_note": "x",
                                     "clear": ["enabled"]}))[0]
                assert cleared["enabled"] is True
            finally:
                await close()


class TestRunReplay:
    async def test_replay_and_unknown_node(self, monkeypatch) -> None:
        from api.app.runs import RunService

        _setup(monkeypatch)
        import api.app.mcp.tools_writes as writes

        service = RunService(scanner=None, history=None, executor=None,  # type: ignore[arg-type]
                             writer=FakeAudit())

        def fake_replay(run_id: str, node: str, *, actor_user_id: str):
            if node not in ("trend_research",):
                from api.app.runs import UnknownNode

                raise UnknownNode(f"unknown node {node!r}")
            return {"run_id": run_id, "node": node, "status": "in_flight"}

        monkeypatch.setattr(service, "replay", fake_replay)
        monkeypatch.setattr(writes, "_run_service", lambda: service)
        async with LiveMCP(_app()) as url:
            session, close = await _session(url, "sdr_test")
            try:
                body = _items(await session.call_tool(
                    "run_replay", {"run_id": "run-1", "node": "trend_research"}))[0]
                assert body["status"] == "in_flight"
                bad = await session.call_tool(
                    "run_replay", {"run_id": "run-1", "node": "nope"})
                assert bad.is_error and "unknown node" in _text(bad)
            finally:
                await close()
