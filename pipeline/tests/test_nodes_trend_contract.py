"""Nodes 1–2 contracts (spec C2 nodes 1–2, C3, C4).

Scoring rubric boundaries (locked weights), deterministic clustering with a
mocked LLM, contract-draft shape validation against §1.1, interrupt + resume
paths, cost-row capture, and graph wiring — all offline.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from pipeline.graph import build_graph
from pipeline.llm import OpenRouterClient
from pipeline.nodes.contract import (
    contract_approval,
    draft_contract,
    slugify,
    validate_contract,
)
from pipeline.nodes.trend import (
    MAX_ENGAGEMENT,
    MAX_NOVELTY,
    MAX_SPECIFICITY,
    PASS_THRESHOLD,
    cluster_briefs,
    score_brief,
    trend_research,
)
from pipeline.routing import GEMINI_FLASH_LITE, NODE_ORDER

BRIEFS = [
    {"id": "b1", "subject": "Vibe Coding", "text": "tee about vibe coding", "style": "mono-log",
     "engagement": 35, "novelty": 20, "specificity": 15},  # total 70 — pass
    {"id": "b2", "subject": "Vibe Coding", "text": "hoodie about vibe coding", "style": "mono-log",
     "engagement": 30, "novelty": 20, "specificity": 12},  # total 62 — pass
    {"id": "b3", "subject": "Stale Meme", "text": "outdated joke", "style": "pixel",
     "engagement": 10, "novelty": 5, "specificity": 5},  # total 20 — fail
]


def _client(reply: Any, captured: list[dict], usage: dict | None = None) -> OpenRouterClient:
    body = reply if isinstance(reply, str) else json.dumps(reply)

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": body}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8, **(usage or {})},
            },
        )

    return OpenRouterClient(api_key="test-key", transport=httpx.MockTransport(handler))


class _FakeEngine:
    def __init__(self, fail: bool = False) -> None:
        self.rows: list[dict] = []
        self.fail = fail

    @contextmanager
    def begin(self):
        engine = self

        class _Conn:
            def execute(self, stmt):
                if engine.fail:
                    raise RuntimeError("db down")
                engine.rows.append(dict(stmt.compile().params))

        yield _Conn()


# ------------------------------------------------------------------ scoring


def test_pass_threshold_boundary() -> None:
    assert PASS_THRESHOLD == 60
    assert score_brief(30, 20, 10)["passed"] is True  # 60 passes
    assert score_brief(30, 20, 9)["passed"] is False  # 59 fails
    assert score_brief(31, 20, 10)["passed"] is True  # 61 passes


def test_locked_weight_maxima() -> None:
    assert (MAX_ENGAGEMENT, MAX_NOVELTY, MAX_SPECIFICITY) == (40, 30, 30)
    assert score_brief(40, 30, 30)["total"] == 100


@pytest.mark.parametrize(
    "args",
    [(41, 0, 0), (0, 31, 0), (0, 0, 31), (-1, 0, 0), (True, 0, 0), ("x", 0, 0)],
)
def test_out_of_range_scores_are_loud(args: tuple) -> None:
    with pytest.raises(ValueError):
        score_brief(*args)


# --------------------------------------------------------------- clustering


def test_clustering_groups_deterministically() -> None:
    captured: list[dict] = []
    client = _client({"clusters": [{"theme": "Vibe Coding", "brief_ids": ["b2", "b1"]}]}, captured)
    clusters, result = cluster_briefs(BRIEFS[:2], client, GEMINI_FLASH_LITE)
    assert len(captured) == 1  # exactly one synthesis call
    assert clusters == [{"cluster_id": "cluster-1", "theme": "Vibe Coding", "brief_ids": ["b1", "b2"]}]
    assert result is not None


def test_clustering_rejects_unknown_ids() -> None:
    captured: list[dict] = []
    client = _client({"clusters": [{"theme": "X", "brief_ids": ["ghost"]}]}, captured)
    with pytest.raises(ValueError, match="unknown brief IDs"):
        cluster_briefs(BRIEFS[:1] + BRIEFS[1:2], client, "m")


def test_clustering_rejects_non_json() -> None:
    captured: list[dict] = []
    client = _client("just some prose, no json", captured)
    with pytest.raises(ValueError, match="did not return JSON"):
        cluster_briefs(BRIEFS[:2], client, "m")


def test_trivial_inputs_skip_the_model_call() -> None:
    captured: list[dict] = []
    client = _client({"clusters": []}, captured)
    clusters, result = cluster_briefs([], client, "m")
    assert (clusters, result) == ([], None)
    clusters, result = cluster_briefs([BRIEFS[0]], client, "m")
    assert result is None and clusters[0]["brief_ids"] == ["b1"]
    assert captured == []


def test_briefs_need_ids() -> None:
    captured: list[dict] = []
    with pytest.raises(ValueError, match="'id'"):
        cluster_briefs([{"subject": "no id"}], _client({"clusters": []}, captured), "m")


# -------------------------------------------------------------- trend node


def test_trend_node_filters_and_clusters() -> None:
    captured: list[dict] = []
    client = _client(
        {"clusters": [{"theme": "Vibe Coding", "brief_ids": ["b1", "b2"]}]},
        captured,
        usage={"cost": 0.004},
    )
    engine = _FakeEngine()
    out = trend_research(
        {"briefs": BRIEFS},
        {"configurable": {"llm_client": client, "cost_engine": engine}},  # type: ignore[typeddict-item]
    )
    assert out["visited"] == ["trend_research"]
    assert out["clusters"] == [
        {"cluster_id": "cluster-1", "theme": "Vibe Coding", "brief_ids": ["b1", "b2"]}
    ]
    assert "errors" not in out
    assert engine.rows[0] == {
        "node": "trend_research",
        "model": GEMINI_FLASH_LITE,
        "tokens_in": 12,
        "tokens_out": 8,
        "cost_usd": 0.004,
    }


def test_trend_node_records_cost_failure_without_crashing() -> None:
    captured: list[dict] = []
    client = _client({"clusters": [{"theme": "T", "brief_ids": ["b1", "b2"]}]}, captured)
    out = trend_research(
        {"briefs": BRIEFS[:2]},
        {"configurable": {"llm_client": client, "cost_engine": _FakeEngine(fail=True)}},  # type: ignore[typeddict-item]
    )
    assert out["clusters"][0]["cluster_id"] == "cluster-1"
    assert any("cost logging failed" in e and "db down" in e for e in out["errors"])


def test_trend_node_missing_engine_is_recorded() -> None:
    captured: list[dict] = []
    client = _client({"clusters": [{"theme": "T", "brief_ids": ["b1", "b2"]}]}, captured)
    out = trend_research({"briefs": BRIEFS[:2]}, {"configurable": {"llm_client": client}})  # type: ignore[typeddict-item]
    assert any("no cost_engine" in e for e in out["errors"])


def test_trend_node_empty_briefs_needs_no_client() -> None:
    assert trend_research({"briefs": []}, None) == {"clusters": [], "visited": ["trend_research"]}


def test_trend_node_malformed_brief_is_loud() -> None:
    with pytest.raises(ValueError, match="missing score fields"):
        trend_research({"briefs": [{"id": "b9"}]}, None)


# --------------------------------------------------------------- contract


def _cluster() -> dict[str, Any]:
    return {"cluster_id": "cluster-1", "theme": "Vibe Coding Tees", "brief_ids": ["b1", "b2"]}


def test_draft_validates_clean_against_schema() -> None:
    draft = draft_contract(_cluster(), ["mono-log", "mono-log"])
    assert validate_contract(draft) == []
    assert draft["status"] == "draft" and draft["approved_at"] is None
    assert draft["collection_id"] == "vibe-coding-tees"
    assert draft["style_archetype"] == "mono-log"
    assert draft["illustration_rules"]["no_mixed_styles"] is True


def test_draft_style_tiebreak_is_deterministic() -> None:
    draft = draft_contract(_cluster(), ["zeta", "alpha"])
    assert draft["style_archetype"] == "alpha"


def test_draft_needs_member_styles() -> None:
    with pytest.raises(ValueError, match="no member styles"):
        draft_contract(_cluster(), [])


def test_slugify() -> None:
    assert slugify("Vibe Coding Tees!!") == "vibe-coding-tees"


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda d: d.update(status="live"), "status must be one of"),
        (lambda d: d.update(style_archetype=""), "style_archetype"),
        (lambda d: d["illustration_rules"].update(no_mixed_styles=False), "no_mixed_styles"),
        (lambda d: d.update(placement_templates=[{"design_type": "emoji", "front": "chest", "back": "none", "sleeve": "none"}]), "design_type"),
        (lambda d: d.update(placement_templates=[{"design_type": "hero-icon", "front": "side", "back": "none", "sleeve": "none"}]), "front/back"),
        (lambda d: d.update(extra_field=1), "unknown fields"),
        (lambda d: d.pop("theme"), "missing fields"),
        (lambda d: d.update(product_count_target=0), "product_count_target"),
        (lambda d: d["kpi_thresholds"].update(min_units=-1), "kpi_thresholds.min_units"),
    ],
)
def test_validate_contract_rejects(mutate, fragment: str) -> None:
    draft = draft_contract(_cluster(), ["mono-log"])
    mutate(draft)
    assert any(fragment in e for e in validate_contract(draft)), validate_contract(draft)


# ------------------------------------------------------- interrupt + resume


def _briefs_state() -> dict[str, Any]:
    return {"design_id": "d-11", "briefs": BRIEFS}


def test_contract_node_pauses_with_drafts_and_resumes() -> None:
    graph = build_graph(checkpointer=MemorySaver())
    captured: list[dict] = []
    client = _client({"clusters": [{"theme": "Vibe Coding", "brief_ids": ["b1", "b2"]}]}, captured)
    base = {
        "thread_id": "n2-pause",
        "hitl": {"trend_research": False, "contract_approval": True},
        "llm_client": client,
        "cost_engine": _FakeEngine(),
    }
    paused = graph.invoke(_briefs_state(), {"configurable": base})
    assert "__interrupt__" in paused
    payload = paused["__interrupt__"][0].value
    assert payload["node"] == "contract_approval"
    assert payload["contracts"][0]["collection_id"] == "vibe-coding"

    resumed = graph.invoke(
        Command(resume={"approved_cluster_id": "cluster-1"}),
        {"configurable": {**base, "hitl": {}}},
    )
    assert resumed["collection_contract"]["collection_id"] == "vibe-coding"
    assert resumed["collection_contract"]["status"] == "draft"


def test_contract_node_bad_resume_decision_is_recorded() -> None:
    graph = build_graph(checkpointer=MemorySaver())
    captured: list[dict] = []
    client = _client({"clusters": [{"theme": "Vibe Coding", "brief_ids": ["b1", "b2"]}]}, captured)
    base = {
        "thread_id": "n2-bad",
        "hitl": {"trend_research": False, "contract_approval": True},
        "llm_client": client,
        "cost_engine": _FakeEngine(),
    }
    graph.invoke(_briefs_state(), {"configurable": base})
    resumed = graph.invoke(
        Command(resume={"approved_cluster_id": "ghost"}),
        {"configurable": {**base, "hitl": {}}},
    )
    assert resumed["collection_contract"] == {}
    assert any("approved_cluster_id" in e for e in resumed["errors"])


def test_nodes_wired_in_graph_end_to_end() -> None:
    graph = build_graph(checkpointer=MemorySaver())
    captured: list[dict] = []
    client = _client({"clusters": [{"theme": "Vibe Coding", "brief_ids": ["b1", "b2"]}]}, captured)
    off = {n: False for n in NODE_ORDER}
    result = graph.invoke(
        _briefs_state(),
        {"configurable": {"thread_id": "n2-wire", "hitl": off, "llm_client": client,
                           "cost_engine": _FakeEngine()}},
    )
    assert result["visited"] == NODE_ORDER
    assert result["clusters"][0]["theme"] == "Vibe Coding"
    assert result["collection_contract"]["collection_id"] == "vibe-coding"


def test_empty_clusters_record_error_without_interrupt() -> None:
    out = contract_approval({"clusters": []}, {"configurable": {"hitl": {"contract_approval": True}}})  # type: ignore[typeddict-item]
    assert out["collection_contract"] == {}
    assert any("no clusters" in e for e in out["errors"])
