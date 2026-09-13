"""Nodes 6–8 contracts (spec C8, C9, C2 nodes 6–8).

Deterministic placement table, rubric threshold boundaries, regen cap +
feedback propagation, human-review exhaustion, technical-QC rejections —
all offline with mocked transports.
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
from langgraph.types import Command

from pipeline import rubric
from pipeline.graph import build_graph
from pipeline.llm import OpenRouterClient
from pipeline.nodes.aesthetic_qc import aesthetic_qc
from pipeline.nodes.placement import placement, resolve_placement
from pipeline.nodes.technical_qc import inspect_png, technical_qc
from pipeline.routing import NODE_ORDER

CONTRACT = {
    "collection_id": "vibe-coding",
    "theme": "Vibe Coding",
    "status": "draft",
    "style_archetype": "mono-log",
    "illustration_rules": {"line_weight": None, "palette": ["#0D0D0D"], "no_mixed_styles": True},
    "garment_colorways": [
        {"base": "black", "contrast_pass": True},
        {"base": "charcoal", "contrast_pass": True},
        {"base": "white", "contrast_pass": False},
    ],
    "placement_templates": [
        {"design_type": "hero-icon", "front": "chest", "back": "none", "sleeve": "none"},
        {"design_type": "wordmark", "front": "none", "back": "full", "sleeve": "none"},
    ],
}


def _png_bytes(color_type: int = 6, width: int = 256, height: int = 256) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + ihdr
        + b"\x00" * 4
        + b"\x00\x00\x00\x00IEND"
    )


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


def _vision_client(scores_list: list[dict], captured: list[dict]) -> OpenRouterClient:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        content = body["messages"][0]["content"]
        text = (
            " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            if isinstance(content, list)
            else content
        )
        captured.append(text)
        reply = scores_list[min(calls["n"], len(scores_list) - 1)]
        calls["n"] += 1
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(reply)}}], "usage": {}}
        )

    return OpenRouterClient(api_key="test-key", transport=httpx.MockTransport(handler))


def _image_client(captured: list[dict]) -> OpenRouterClient:
    payload = base64.b64encode(_png_bytes()).decode()

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"b64_json": payload}], "usage": {}})

    return OpenRouterClient(api_key="test-key", transport=httpx.MockTransport(handler))


def _render_state(tmp_path: Path, **overrides: Any) -> dict[str, Any]:
    artifact = tmp_path / "render.png"
    artifact.write_bytes(_png_bytes())
    state: dict[str, Any] = {
        "design_id": "d-6",
        "collection_contract": CONTRACT,
        "design_spec": {"render_prompt": "a monochrome terminal", "style": "mono-log",
                        "brief_subject": "Vibe Coding"},
        "render_result": {"file_url": str(artifact), "model_used": "riverflow-v2-pro",
                          "colorways_valid": []},
        "render": {"file_url": str(artifact), "model_used": "riverflow-v2-pro",
                   "colorways_valid": []},
    }
    state.update(overrides)
    return state


def _cfg(client=None, **extra):
    cfg: dict[str, Any] = {}
    if client is not None:
        cfg["llm_client"] = client
    cfg["cost_engine"] = _FakeEngine()
    cfg.update(extra)
    return {"configurable": cfg}


# --------------------------------------------------------------- placement


def test_placement_determinism_table() -> None:
    first = resolve_placement(CONTRACT, "hero-icon")
    assert first == {
        "design_type": "hero-icon",
        "zones": {"front": "chest", "back": "none", "sleeve": "none"},
        "colorways_valid": ["black", "charcoal"],  # white excluded: contrast fail
    }
    assert first == resolve_placement(CONTRACT, "hero-icon")  # deterministic
    wordmark = resolve_placement(CONTRACT, "wordmark")
    assert wordmark["zones"] == {"front": "none", "back": "full", "sleeve": "none"}
    assert wordmark["colorways_valid"] == ["black", "charcoal"]


def test_placement_unknown_type_is_loud() -> None:
    with pytest.raises(ValueError, match="no placement template"):
        resolve_placement(CONTRACT, "emoji")


def test_placement_node_fills_zones_and_colorways(tmp_path: Path) -> None:
    out = placement(_render_state(tmp_path), _cfg(design_type="hero-icon"))
    assert out["placement"] == {"front": "chest", "back": "none", "sleeve": "none"}
    assert out["render"]["colorways_valid"] == ["black", "charcoal"]
    assert out["render_result"]["colorways_valid"] == ["black", "charcoal"]
    assert out["visited"] == ["placement"]


@pytest.mark.parametrize(
    ("state_patch", "cfg_patch", "fragment"),
    [
        ({}, {"design_type": "hero-icon"}, "no collection contract"),
        ({"collection_contract": CONTRACT}, {}, "no design_type"),
        ({"collection_contract": CONTRACT}, {"design_type": "emoji"}, "no placement template"),
    ],
)
def test_placement_node_missing_inputs_record_errors(
    tmp_path: Path, state_patch: dict, cfg_patch: dict, fragment: str
) -> None:
    base = _render_state(tmp_path)
    base.update(state_patch)
    if "collection_contract" not in state_patch:
        base.pop("collection_contract")
    out = placement(base, _cfg(**cfg_patch))
    assert out["placement"] == {}
    assert any(fragment in e for e in out["errors"])


# ------------------------------------------------------------------ rubric


def test_rubric_threshold_boundaries() -> None:
    assert rubric.PASS_THRESHOLD == 70
    good = {"style_cohesion": 80, "focal_point": 80, "placement_fit": 80, "contrast": 80}
    assert rubric.evaluate(good)["result"] == "pass"
    for criterion in rubric.CRITERIA:
        failing = dict(good, **{criterion: 69})
        evaluated = rubric.evaluate(failing)
        assert evaluated["result"] == "fail"
        assert evaluated["failing"] == [criterion]
        assert rubric.evaluate(dict(good, **{criterion: 70}))["result"] == "pass"
        assert rubric.evaluate(dict(good, **{criterion: 71}))["result"] == "pass"


@pytest.mark.parametrize(
    "payload",
    [
        {"style_cohesion": 80, "focal_point": 80, "placement_fit": 80},  # missing key
        {"style_cohesion": 80, "focal_point": 80, "placement_fit": 80, "contrast": 101},
        {"style_cohesion": 80, "focal_point": 80, "placement_fit": 80, "contrast": True},
        "not a mapping",
    ],
)
def test_rubric_rejects_malformed_scores(payload) -> None:
    with pytest.raises(ValueError):
        rubric.parse_scores(payload)


def test_regen_cap_is_a_constant() -> None:
    assert rubric.MAX_REGEN_RETRIES == 2


def test_rejection_feedback_names_criterion_and_score() -> None:
    evaluation = rubric.evaluate(
        {"style_cohesion": 80, "focal_point": 80, "placement_fit": 80, "contrast": 40}
    )
    feedback = rubric.rejection_feedback(evaluation, 1)
    assert "contrast" in feedback and "40" in feedback


# ------------------------------------------------------------ aesthetic QC


PASS_SCORES = {"style_cohesion": 80, "focal_point": 85, "placement_fit": 90, "contrast": 75}
FAIL_SCORES = {"style_cohesion": 80, "focal_point": 85, "placement_fit": 90, "contrast": 40}


def test_aesthetic_qc_pass_continues(tmp_path: Path) -> None:
    captured: list[dict] = []
    out = aesthetic_qc(
        _render_state(tmp_path), _cfg(_vision_client([PASS_SCORES], captured))
    )
    assert out["aesthetic_qc"]["result"] == "pass"
    assert out["aesthetic_qc"]["attempts"] == 1
    assert "render_feedback" not in out
    assert out["visited"] == ["aesthetic_qc"]


def test_aesthetic_qc_fail_sets_feedback(tmp_path: Path) -> None:
    captured: list[dict] = []
    out = aesthetic_qc(
        _render_state(tmp_path), _cfg(_vision_client([FAIL_SCORES], captured))
    )
    assert out["aesthetic_qc"]["result"] == "fail"
    assert "contrast" in out["render_feedback"] and "40" in out["render_feedback"]


def test_regen_receives_previous_feedback(tmp_path: Path) -> None:
    captured: list[dict] = []
    client = _vision_client([FAIL_SCORES, PASS_SCORES], captured)
    first = aesthetic_qc(_render_state(tmp_path), _cfg(client))
    assert first["aesthetic_qc"]["result"] == "fail"
    resumed_state = {**_render_state(tmp_path), "aesthetic_qc": first["aesthetic_qc"],
                     "render_feedback": first["render_feedback"]}
    second = aesthetic_qc(resumed_state, _cfg(client))
    assert second["aesthetic_qc"]["result"] == "pass"
    assert second["aesthetic_qc"]["attempts"] == 2
    assert "Regeneration required" in captured[1]  # prior feedback in the prompt


def test_aesthetic_qc_missing_render_records_error() -> None:
    out = aesthetic_qc({}, None)
    assert out["aesthetic_qc"]["result"] == "fail"
    assert any("no render" in e for e in out["errors"])


# ------------------------------------------------------------ technical QC


@pytest.mark.parametrize(
    ("data", "passed", "fragment"),
    [
        (_png_bytes(color_type=6), True, "alpha channel present"),
        (_png_bytes(color_type=4), True, "alpha channel present"),
        (_png_bytes(color_type=2), False, "missing alpha channel"),
        (b"not an image", False, "not a PNG"),
        (_png_bytes()[:20], False, "truncated"),
    ],
)
def test_technical_qc_verdicts(tmp_path: Path, data: bytes, passed: bool, fragment: str) -> None:
    artifact = tmp_path / "render.png"
    artifact.write_bytes(data)
    out = technical_qc({"render_result": {"file_url": str(artifact)}}, None)
    assert out["technical_qc"]["passed"] is passed
    assert any(fragment in c for c in out["technical_qc"]["checks"])
    assert out["visited"] == ["technical_qc"]


def test_technical_qc_missing_render_records_error() -> None:
    out = technical_qc({}, None)
    assert out["technical_qc"]["passed"] is False
    assert any("no render" in e for e in out["errors"])


def test_technical_qc_unreadable_artifact_records_error(tmp_path: Path) -> None:
    out = technical_qc({"render_result": {"file_url": str(tmp_path / "ghost.png")}}, None)
    assert out["technical_qc"]["passed"] is False
    assert any("cannot read" in e for e in out["errors"])


# --------------------------------------------------- regen loop + edges


def _regen_graph(tmp_path: Path, scores: list[dict], flags: dict | None = None):
    vision_captured: list[dict] = []
    image_captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/generations"):
            body = json.loads(request.content)
            image_captured.append(body)
            payload = base64.b64encode(_png_bytes()).decode()
            return httpx.Response(200, json={"data": [{"b64_json": payload}], "usage": {}})
        content = json.loads(request.content)["messages"][0]["content"]
        prompt = (
            " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            if isinstance(content, list)
            else content
        )
        if "thematic clusters" in prompt:
            reply = {"clusters": [{"theme": "Vibe Coding", "brief_ids": ["b1", "b2"]}]  }
        elif "listing copy" in prompt:
            reply = {"slogan": "Ship It Live", "title": "Vibe Coding Tee",
                     "description": "A dry joke.", "tags": ["vibe-coding"]}
        elif "RCAO" in prompt:
            reply = {"rcao": "r", "render_prompt": "a monochrome terminal"}
        else:
            vision_captured.append(prompt)
            reply = scores[min(len(vision_captured) - 1, len(scores) - 1)]
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(reply)}}], "usage": {}}
        )

    client = OpenRouterClient(api_key="test-key", transport=httpx.MockTransport(handler))
    graph = build_graph(checkpointer=MemorySaver())
    off = {n: False for n in NODE_ORDER}
    if flags:
        off.update(flags)
    base = {
        "thread_id": "regen",
        "hitl": off,
        "llm_client": client,
        "cost_engine": _FakeEngine(),
        "run_dir": str(tmp_path),
        "design_type": "hero-icon",
    }
    state = {
        "design_id": "d-regen",
        "brief": {"subject": "Vibe Coding", "text": "x", "style": "mono-log"},
        "briefs": [
            {"id": "b1", "subject": "Vibe Coding", "text": "tee", "style": "mono-log",
             "engagement": 35, "novelty": 20, "specificity": 15},
            {"id": "b2", "subject": "Vibe Coding", "text": "hoodie", "style": "mono-log",
             "engagement": 30, "novelty": 20, "specificity": 12},
        ],
    }
    return graph, base, state, vision_captured, image_captured


def test_regen_loop_rerenders_with_feedback_then_passes(tmp_path: Path) -> None:
    graph, base, state, vision_captured, image_captured = _regen_graph(
        tmp_path, [FAIL_SCORES, PASS_SCORES]
    )
    result = graph.invoke(state, {"configurable": base})
    assert len(image_captured) == 2  # initial + 1 regen
    assert "Regeneration required" in vision_captured[1]  # feedback reached scoring
    assert image_captured[1]["prompt"].startswith("a monochrome terminal")
    assert "REGENERATION FEEDBACK" in image_captured[1]["prompt"]  # ...and the render
    assert result["aesthetic_qc"]["result"] == "pass"
    assert result["aesthetic_qc"]["attempts"] == 2
    assert result["render_feedback"] == ""  # consumed, not accumulated
    assert (tmp_path / "render.png").exists() and (tmp_path / "render-r2.png").exists()


def test_regen_cap_falls_to_human_review(tmp_path: Path) -> None:
    graph, base, state, _, image_captured = _regen_graph(
        tmp_path, [FAIL_SCORES], flags={"aesthetic_qc": True}
    )
    paused = graph.invoke(state, {"configurable": {**base, "thread_id": "regen-cap"}})
    assert "__interrupt__" in paused
    payload = paused["__interrupt__"][0].value
    assert payload["status"] == "awaiting_human_review"
    assert payload["attempts"] == rubric.MAX_REGEN_RETRIES + 1
    assert payload["failing"] == ["contrast"]
    assert len(image_captured) == rubric.MAX_REGEN_RETRIES + 1  # capped, then human

    resumed = graph.invoke(
        Command(resume={"decision": "approved"}),
        {"configurable": {**base, "thread_id": "regen-cap"}},
    )
    assert resumed["aesthetic_qc"]["result"] == "fail-human-review"
    assert "technical_qc" in resumed["visited"]  # run continues; human owns verdict


def test_regen_cap_without_hitl_records_error(tmp_path: Path) -> None:
    graph, base, state, _, image_captured = _regen_graph(tmp_path, [FAIL_SCORES])
    result = graph.invoke(state, {"configurable": {**base, "thread_id": "regen-nohitl"}})
    assert len(image_captured) == rubric.MAX_REGEN_RETRIES + 1
    assert any("HITL off" in e for e in result["errors"])
    assert result["visited"].count("art_render") == rubric.MAX_REGEN_RETRIES + 1
