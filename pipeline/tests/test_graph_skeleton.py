"""Graph skeleton, checkpointer wiring, and cost-logging contracts (spec C1, C4).

Proves: the locked 11-node graph compiles; a full run with HITL flags off
executes nodes in order; HITL is a pure config flag (defaults interrupt,
all-off runs through, resume-after-toggle completes); run state is inspectable
from the checkpointer with the §1.3 design-record shape; cost records have the
exact payload shape and logging failures surface without crashing.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import get_type_hints

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from pipeline.checkpoint import get_checkpointer
from pipeline.costs import (
    build_cost_record,
    model_calls,
    record_cost,
    to_payload,
)
from pipeline.graph import DEFAULT_HITL, build_graph, register_node
from pipeline.routing import NODE_ORDER
from pipeline.state import RunState


def _off(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id, "hitl": {n: False for n in NODE_ORDER}}}


def test_graph_compiles() -> None:
    assert build_graph(checkpointer=MemorySaver()) is not None


def test_full_run_executes_locked_order() -> None:
    graph = build_graph(checkpointer=MemorySaver())
    result = graph.invoke({"design_id": "d-1", "collection_id": "c-1"}, _off("full-run"))
    assert result["visited"] == NODE_ORDER


def test_state_carries_design_record_shape() -> None:
    hints = get_type_hints(RunState)
    for key in ("design_id", "collection_id", "brief", "render", "qc_scores", "placement"):
        assert key in hints


def test_run_state_inspectable_from_checkpointer() -> None:
    graph = build_graph(checkpointer=MemorySaver())
    graph.invoke({"design_id": "d-9", "collection_id": "c-9"}, _off("inspect"))
    snapshot = graph.get_state({"configurable": {"thread_id": "inspect"}})
    assert snapshot.values["design_id"] == "d-9"
    assert snapshot.values["visited"] == NODE_ORDER


def test_hitl_defaults_match_vision_table() -> None:
    """Vision §3.2 defaults: gates on nodes 2/7/10, off everywhere else.

    (PBI-011: placeholders for nodes 1–2 are real now, so the behavioral
    default-interrupt assertion lives in test_nodes_trend_contract.py, where
    the contract node pauses with drafts. An empty run records the missing
    input as an error instead of interrupting on nothing.)
    """
    assert DEFAULT_HITL == {
        "trend_research": False,
        "contract_approval": True,
        "listing_copy": False,
        "design_spec": False,
        "art_render": False,
        "placement": False,
        "aesthetic_qc": True,
        "technical_qc": False,
        "fw_create": False,
        "publish_gate": True,
        "shelf": False,
    }
    graph = build_graph(checkpointer=MemorySaver())
    result = graph.invoke({"design_id": "d-2"}, {"configurable": {"thread_id": "defaults"}})
    # Empty input: node 2 records an error instead of interrupting on nothing;
    # the run then pauses at node 7, the next default-on gate.
    assert "__interrupt__" in result
    assert result["visited"] == NODE_ORDER[:6]


def test_hitl_toggle_is_config_not_structure() -> None:
    """Same compiled graph: interrupt, flip flags, resume to completion."""
    graph = build_graph(checkpointer=MemorySaver())
    paused = graph.invoke(
        {"design_id": "d-3"},
        {"configurable": {"thread_id": "toggle", "hitl": {"contract_approval": True}}},
    )
    assert "__interrupt__" in paused
    resumed = graph.invoke(
        Command(resume="approved"),
        {"configurable": {"thread_id": "toggle", "hitl": {n: False for n in NODE_ORDER}}},
    )
    assert resumed["visited"] == NODE_ORDER


def test_register_node_rejects_unknown() -> None:
    with pytest.raises(KeyError):
        register_node("not_a_node", lambda s, c=None: {})


def test_checkpointer_defaults_to_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert isinstance(get_checkpointer(), MemorySaver)


def test_checkpointer_uses_postgres_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    # v3 from_conn_string() yields an async CM (not the saver); entering it
    # would connect, so the offline test only asserts the CM protocol.
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    checkpointer = get_checkpointer()
    assert hasattr(checkpointer, "__aenter__") and hasattr(checkpointer, "__aexit__")


def test_cost_record_payload_shape() -> None:
    record = build_cost_record("art_render", "riverflow-v2-pro", 10, 5, 0.012)
    assert to_payload(record) == {
        "node": "art_render",
        "model": "riverflow-v2-pro",
        "tokens_in": 10,
        "tokens_out": 5,
        "cost_usd": 0.012,
    }


def test_cost_record_requires_node_and_model() -> None:
    with pytest.raises(ValueError):
        build_cost_record("", "some-model")
    with pytest.raises(ValueError):
        build_cost_record("art_render", "")


def test_cost_table_mirrors_migration() -> None:
    # Guards drift between costs.py and api/migrations/0002_model_calls.sql.
    assert {c.name for c in model_calls.columns} == {
        "id",
        "node",
        "model",
        "tokens_in",
        "tokens_out",
        "cost_usd",
        "created_at",
    }


class _FakeConn:
    def __init__(self) -> None:
        self.params: list[dict] = []

    def execute(self, stmt):
        self.params.append(dict(stmt.compile().params))


class _FakeEngine:
    def __init__(self) -> None:
        self.conn = _FakeConn()

    @contextmanager
    def begin(self):
        yield self.conn


def test_cost_record_success_path_offline() -> None:
    engine = _FakeEngine()
    record = build_cost_record("trend_research", "google/gemini-2.0-flash-001", 7, 3, 0.001)
    outcome = record_cost(record, engine)  # type: ignore[arg-type]
    assert outcome.ok and outcome.error is None
    assert engine.conn.params[0] == {
        "node": "trend_research",
        "model": "google/gemini-2.0-flash-001",
        "tokens_in": 7,
        "tokens_out": 3,
        "cost_usd": 0.001,
    }


def test_cost_failure_surfaces_without_crashing() -> None:
    class BrokenEngine:
        def begin(self):
            raise RuntimeError("db down")

    outcome = record_cost(build_cost_record("shelf", "none", 0, 0, 0.0), BrokenEngine())  # type: ignore[arg-type]
    assert outcome.ok is False
    assert outcome.error is not None and "db down" in outcome.error
