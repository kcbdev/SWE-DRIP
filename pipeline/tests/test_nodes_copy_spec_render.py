"""Nodes 3–5 contracts (spec C2 nodes 3–5, C3, C4, parity shape C7).

Brand-locked copy rules, contract-field inheritance (no per-design invention),
primary→fallback render with pre-write PNG validation — all offline with
mocked transports.
"""

from __future__ import annotations

import base64
import json
import struct
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from langgraph.checkpoint.memory import MemorySaver

from pipeline.graph import build_graph
from pipeline.llm import OpenRouterClient
from pipeline.nodes.copy import TITLE_MAX_CHARS, SLOGAN_MAX_WORDS, listing_copy, validate_copy
from pipeline.nodes.design_spec import INHERITED_KEYS, design_spec
from pipeline.nodes.render import art_render, parse_png_dimensions
from pipeline.routing import NODE_ORDER

BRIEF = {"subject": "Vibe Coding", "text": "a tee about vibe coding", "style": "mono-log"}

CONTRACT = {
    "collection_id": "vibe-coding",
    "theme": "Vibe Coding",
    "status": "draft",
    "style_archetype": "mono-log",
    "illustration_rules": {"line_weight": None, "palette": ["#0D0D0D", "#00FF41"], "no_mixed_styles": True},
    "garment_colorways": [],
    "placement_templates": [{"design_type": "hero-icon", "front": "chest", "back": "none", "sleeve": "none"}],
    "product_count_target": None,
    "lifecycle_days": None,
    "kpi_thresholds": {"min_units": None, "min_conversion": None, "eval_window_days": None},
    "created_by": "system",
    "created_at": "2026-09-13T00:00:00+00:00",
    "approved_at": None,
    "retired_at": None,
}

GOOD_COPY = {
    "slogan": "Ship It Live",  # 3 words
    "title": "Vibe Coding Tee",
    "description": "A dry joke for developers who review diffs.",
    "tags": ["vibe-coding", "developer-tee"],
}


def _png_bytes(width: int = 256, height: int = 256) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4 + b"\x00\x00\x00\x00IEND"


def _chat_client(reply: Any, captured: list[dict]) -> OpenRouterClient:
    body = reply if isinstance(reply, str) else json.dumps(reply)

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"message": {"content": body}}], "usage": {"prompt_tokens": 5, "completion_tokens": 5}}
        )

    return OpenRouterClient(api_key="test-key", transport=httpx.MockTransport(handler))


class _FakeEngine:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    @contextmanager
    def begin(self):
        engine = self

        class _Conn:
            def execute(self, stmt):
                engine.rows.append(dict(stmt.compile().params))

        yield _Conn()


def _cfg(client, engine=None, **extra):
    cfg: dict[str, Any] = {"llm_client": client}
    if engine is not None:
        cfg["cost_engine"] = engine
    cfg.update(extra)
    return {"configurable": cfg}


# ------------------------------------------------------------------- copy


def test_copy_constraints_are_brand_locked() -> None:
    assert (SLOGAN_MAX_WORDS, TITLE_MAX_CHARS) == (6, 60)
    assert validate_copy(GOOD_COPY) == []


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda c: c.update(slogan="one two three four five six seven"), "slogan must be"),
        (lambda c: c.update(title="t" * 61), "title must be"),
        (lambda c: c.update(description=""), "description must be"),
        (lambda c: c.update(tags=[]), "tags must be"),
        (lambda c: c.update(slogan="Ship #It Live"), "must not contain hashtags"),
        (lambda c: c.update(tags=["#vibe"]), "must not contain hashtags"),
    ],
)
def test_copy_rule_violations(mutate, fragment: str) -> None:
    copy = dict(GOOD_COPY)
    mutate(copy)
    assert any(fragment in e for e in validate_copy(copy)), validate_copy(copy)


def test_copy_node_stores_validated_copy_and_cost() -> None:
    captured: list[dict] = []
    engine = _FakeEngine()
    out = listing_copy({"brief": BRIEF}, _cfg(_chat_client(GOOD_COPY, captured), engine))
    assert out["listing_copy"] == GOOD_COPY
    assert out["visited"] == ["listing_copy"]
    assert "errors" not in out
    assert captured[0]["model"] == "anthropic/claude-sonnet-4-6"
    assert engine.rows[0]["node"] == "listing_copy"


def test_copy_node_rejects_violations_loudly() -> None:
    captured: list[dict] = []
    bad = dict(GOOD_COPY, slogan="one two three four five six seven")
    with pytest.raises(ValueError, match="brand-lock violations"):
        listing_copy({"brief": BRIEF}, _cfg(_chat_client(bad, captured)))


def test_copy_node_missing_brief_records_error() -> None:
    out = listing_copy({}, None)
    assert out["listing_copy"] == {}
    assert any("no design brief" in e for e in out["errors"])


# ------------------------------------------------------------------- spec


def test_spec_inherits_contract_fields_verbatim() -> None:
    captured: list[dict] = []
    reasoning = {"rcao": "R:C:A:O reasoning here", "render_prompt": "a monochrome terminal"}
    out = design_spec(
        {"brief": BRIEF, "collection_contract": CONTRACT, "design_id": "d-1"},
        _cfg(_chat_client(reasoning, captured), _FakeEngine()),
    )
    spec = out["design_spec"]
    # Forced inheritance — these come ONLY from the contract:
    assert spec["style"] == "mono-log"
    assert spec["palette"] == ["#0D0D0D", "#00FF41"]
    assert spec["placement_templates"] == CONTRACT["placement_templates"]
    # LLM contribution preserved where it belongs:
    assert spec["render_prompt"] == "a monochrome terminal"
    assert spec["rcao"].startswith("R:C:A:O")
    assert set(INHERITED_KEYS) == {"style", "palette", "placement_templates"}


def test_spec_node_missing_inputs_record_errors() -> None:
    assert any("no collection contract" in e for e in design_spec({"brief": BRIEF}, None)["errors"])
    assert any("no design brief" in e for e in design_spec({"collection_contract": CONTRACT}, None)["errors"])


def test_spec_node_rejects_empty_render_prompt() -> None:
    captured: list[dict] = []
    with pytest.raises(ValueError, match="no render_prompt"):
        design_spec(
            {"brief": BRIEF, "collection_contract": CONTRACT},
            _cfg(_chat_client({"rcao": "x", "render_prompt": ""}, captured)),
        )


# ----------------------------------------------------------------- render


def test_png_dimension_parser() -> None:
    assert parse_png_dimensions(_png_bytes(640, 480)) == (640, 480)
    with pytest.raises(ValueError, match="not a PNG"):
        parse_png_dimensions(b"definitely not an image")
    with pytest.raises(ValueError, match="truncated"):
        parse_png_dimensions(b"\x89PNG\r\n\x1a\nshort")


def _image_client(captured: list[dict], fail_models: set[str] | None = None) -> OpenRouterClient:
    payload = base64.b64encode(_png_bytes()).decode()

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body)
        if fail_models and body.get("model") in fail_models:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json={"data": [{"b64_json": payload}], "usage": {}})

    return OpenRouterClient(api_key="test-key", transport=httpx.MockTransport(handler))


def _spec_state(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    state = {
        "design_id": "d-5",
        "collection_contract": CONTRACT,
        "design_spec": {"render_prompt": "a monochrome terminal", "style": "mono-log"},
    }
    return state, {"run_dir": str(tmp_path)}


def test_render_primary_model_validated_before_state_write(tmp_path: Path) -> None:
    captured: list[dict] = []
    engine = _FakeEngine()
    state, extra = _spec_state(tmp_path)
    out = art_render(state, _cfg(_image_client(captured), engine, **extra))
    assert captured[0]["model"] == "riverflow-v2-pro"
    ref = out["render_result"]
    assert ref["model_used"] == "riverflow-v2-pro"
    assert (ref["width"], ref["height"]) == (256, 256)
    assert ref["colorways_valid"] == []
    assert Path(ref["file_url"]).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert out["render"]["file_url"] == ref["file_url"]
    assert engine.rows[0]["node"] == "art_render"


def test_render_falls_back_on_primary_failure(tmp_path: Path) -> None:
    captured: list[dict] = []
    state, extra = _spec_state(tmp_path)
    out = art_render(
        state, _cfg(_image_client(captured, fail_models={"riverflow-v2-pro"}), _FakeEngine(), **extra)
    )
    assert [c["model"] for c in captured] == ["riverflow-v2-pro", "gpt-5-image-mini"]
    assert out["render_result"]["model_used"] == "gpt-5-image-mini"


def test_render_total_failure_is_loud(tmp_path: Path) -> None:
    captured: list[dict] = []
    state, extra = _spec_state(tmp_path)
    with pytest.raises(RuntimeError, match="all image models failed"):
        art_render(
            state,
            _cfg(
                _image_client(captured, fail_models={"riverflow-v2-pro", "gpt-5-image-mini", "seedream"}),
                _FakeEngine(),
                **extra,
            ),
        )


def test_render_rejects_non_png_before_state_write(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": [{"b64_json": base64.b64encode(b"junk").decode()}], "usage": {}}
        )

    client = OpenRouterClient(api_key="test-key", transport=httpx.MockTransport(handler))
    state, extra = _spec_state(tmp_path)
    with pytest.raises(ValueError, match="not a PNG"):
        art_render(state, _cfg(client, _FakeEngine(), **extra))
    assert not list(tmp_path.iterdir())


def test_render_node_missing_spec_records_error() -> None:
    out = art_render({}, None)
    assert out["render_result"] == {}
    assert any("no design spec" in e for e in out["errors"])


# ------------------------------------------------------------------ wiring


def test_nodes_3_to_5_wired_end_to_end(tmp_path: Path) -> None:
    briefs = [
        {"id": "b1", "subject": "Vibe Coding", "text": "tee", "style": "mono-log",
         "engagement": 35, "novelty": 20, "specificity": 15},
        {"id": "b2", "subject": "Vibe Coding", "text": "hoodie", "style": "mono-log",
         "engagement": 30, "novelty": 20, "specificity": 12},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path.endswith("/images/generations"):
            payload = base64.b64encode(_png_bytes()).decode()
            return httpx.Response(200, json={"data": [{"b64_json": payload}], "usage": {}})
        prompt = body["messages"][0]["content"]
        if "thematic clusters" in prompt:
            reply = {"clusters": [{"theme": "Vibe Coding", "brief_ids": ["b1", "b2"]}]  }
        elif "listing copy" in prompt:
            reply = GOOD_COPY
        else:
            reply = {"rcao": "r", "render_prompt": "a monochrome terminal"}
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(reply)}}], "usage": {}}
        )

    client = OpenRouterClient(api_key="test-key", transport=httpx.MockTransport(handler))
    engine = _FakeEngine()
    graph = build_graph(checkpointer=MemorySaver())
    result = graph.invoke(
        {"design_id": "d-e2e", "brief": BRIEF, "briefs": briefs},
        {"configurable": {"thread_id": "n3-wire", "hitl": {n: False for n in NODE_ORDER},
                           "llm_client": client, "cost_engine": engine,
                           "run_dir": str(tmp_path)}},
    )
    assert result["visited"] == NODE_ORDER
    assert result["listing_copy"]["slogan"] == "Ship It Live"
    # Style flows briefs → cluster → drafted contract → spec (verbatim inheritance):
    assert result["design_spec"]["style"] == "mono-log"
    assert result["design_spec"]["palette"] == result["collection_contract"]["illustration_rules"]["palette"]
    assert result["render_result"]["model_used"] == "riverflow-v2-pro"
    assert {row["node"] for row in engine.rows} >= {
        "trend_research", "listing_copy", "design_spec", "art_render",
    }
