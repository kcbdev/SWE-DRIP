"""A10/A12 calibration evidence (spec C1/C3).

Pins run through the REAL rubric path (parse_scores → evaluate): the ninja
must fail below 70, the rocket must pass above it. Nothing is hard-coded —
the verdicts fall out of the pinned scores via the production functions, and
the prompt builder is asserted general (criterion names, feedback channel)
rather than fixture-tuned. A12: the regen render prompt must materially
differ from the base prompt and carry the rejection note.
"""

from __future__ import annotations

import base64
import json
import struct
from pathlib import Path
from typing import Any

import httpx

from pipeline import rubric
from pipeline.llm import OpenRouterClient
from pipeline.nodes.aesthetic_qc import aesthetic_qc
from pipeline.nodes.render import art_render

FIXTURES = Path(__file__).parent / "fixtures" / "qc"


def _pin(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _png_bytes(width: int = 256, height: int = 256) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4 + b"\x00\x00\x00\x00IEND"


def _vision_client(scores: dict[str, Any], captured: list[dict]) -> OpenRouterClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(scores)}}], "usage": {}})

    return OpenRouterClient(api_key="calibration-test", transport=httpx.MockTransport(handler))


def _image_client(captured: list[dict]) -> OpenRouterClient:
    payload = base64.b64encode(_png_bytes()).decode()

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"data": [{"b64_json": payload}], "usage": {}})

    return OpenRouterClient(api_key="calibration-test", transport=httpx.MockTransport(handler))


class _NullEngine:
    def record(self, *args: Any, **kwargs: Any) -> None:
        return None


# ------------------------------------------------------------------- A10


def test_threshold_is_locked_at_70() -> None:
    assert rubric.PASS_THRESHOLD == 70  # spec anti-pattern: never retuned silently
    assert _pin("ninja")["pass_threshold"] == 70
    assert _pin("rocket")["pass_threshold"] == 70


def test_ninja_scores_below_threshold() -> None:
    pin = _pin("ninja")
    evaluation = rubric.evaluate(rubric.parse_scores(pin["pinned_vision_response"]))
    assert evaluation["result"] == "fail"
    assert min(evaluation["scores"].values()) < rubric.PASS_THRESHOLD
    assert "style_cohesion" in evaluation["failing"]  # the mixed-style defect shows


def test_rocket_scores_above_threshold() -> None:
    pin = _pin("rocket")
    evaluation = rubric.evaluate(rubric.parse_scores(pin["pinned_vision_response"]))
    assert evaluation["result"] == "pass"
    assert all(score >= rubric.PASS_THRESHOLD for score in evaluation["scores"].values())


def test_pins_match_current_rubric_version() -> None:
    assert _pin("ninja")["rubric_version"] == rubric.RUBRIC_VERSION
    assert _pin("rocket")["rubric_version"] == rubric.RUBRIC_VERSION


def test_rubric_prompt_is_general_not_fixture_tuned() -> None:
    prompt = rubric.build_qc_prompt(design_subject="anything", style="any-style", attempt=1)
    for criterion in rubric.CRITERIA:
        assert criterion in prompt  # scores arbitrary subjects on the same four criteria
    assert "ninja" not in prompt and "rocket" not in prompt


def test_node_verdict_carries_scores_and_rubric_version() -> None:
    """End-to-end through aesthetic_qc with the pinned ninja response."""
    pin = _pin("ninja")
    captured: list[dict] = []
    artifact = Path("/tmp") / "calibration-render.png"
    artifact.write_bytes(_png_bytes())
    state = {
        "design_id": "calibration",
        "brief": {"subject": "Ninja", "text": "x", "style": "mono-log"},
        "render_result": {"file_url": str(artifact)},
    }
    out = aesthetic_qc(
        state,  # type: ignore[arg-type]
        {"configurable": {"llm_client": _vision_client(pin["pinned_vision_response"], captured), "cost_engine": _NullEngine()}},  # type: ignore[typeddict-item]
    )
    verdict = out["aesthetic_qc"]
    assert verdict["result"] == "fail"
    assert verdict["rubric_version"] == rubric.RUBRIC_VERSION
    assert verdict["scores"]["style_cohesion"] == 35


# ------------------------------------------------------------------- A12


def test_regen_prompt_materially_differs_and_carries_note(tmp_path: Path) -> None:
    """A rejection note produces a materially different next render prompt."""
    base_prompt = "Draw a ninja tee, mono-line."
    human_note = "The watercolor half must go — pure mono-line only."
    feedback = human_note  # the channel carries caller notes verbatim (see below)
    first: list[dict] = []
    state = {
        "design_id": "calibration-regen",
        "design_spec": {"render_prompt": base_prompt},
        "render_feedback": "",
    }
    out_base = art_render(
        state,  # type: ignore[arg-type]
        {"configurable": {"llm_client": _image_client(first), "cost_engine": _NullEngine(), "run_dir": str(tmp_path)}},  # type: ignore[typeddict-item]
    )
    second: list[dict] = []
    out_regen = art_render(
        {**state, "render_feedback": feedback},  # type: ignore[dict-item]
        {"configurable": {"llm_client": _image_client(second), "cost_engine": _NullEngine(), "run_dir": str(tmp_path)}},  # type: ignore[typeddict-item]
    )
    base_used = first[0]["prompt"] if "prompt" in first[0] else json.dumps(first[0])
    regen_used = second[0]["prompt"] if "prompt" in second[0] else json.dumps(second[0])
    assert regen_used != base_used  # materially different, not a no-op retry
    assert base_prompt in regen_used  # still the same design brief
    assert human_note in regen_used  # the rejection note is carried in
    assert out_regen["render_feedback"] == ""  # consumed, not accumulated
    assert out_base["render_result"]["file_url"] != out_regen["render_result"]["file_url"]


def test_rejection_feedback_names_failing_criteria() -> None:
    evaluation = rubric.evaluate(rubric.parse_scores(_pin("ninja")["pinned_vision_response"]))
    feedback = rubric.rejection_feedback(evaluation, 1)
    assert "style_cohesion" in feedback and "35" in feedback


# ------------------------------------------------------------------- style (PBI-051)


def test_style_betrayal_fails_naming_the_criterion() -> None:
    pin = _pin("style_fail")
    evaluation = rubric.evaluate(rubric.parse_scores(pin["pinned_vision_response"]))
    assert evaluation["result"] == "fail"
    assert evaluation["style_status"] == "fail"
    assert "style_conformance" in evaluation["failing"]
    feedback = rubric.rejection_feedback(evaluation, 1)
    assert "style_conformance" in feedback and "40" in feedback


def test_style_faithful_passes() -> None:
    pin = _pin("style_pass")
    evaluation = rubric.evaluate(rubric.parse_scores(pin["pinned_vision_response"]))
    assert evaluation["result"] == "pass"
    assert evaluation["style_status"] == "pass"


def test_missing_style_is_unscored_not_failed() -> None:
    evaluation = rubric.evaluate(rubric.parse_scores(_pin("rocket")["pinned_vision_response"]))
    assert evaluation["result"] == "pass"
    assert evaluation["style_status"] == "unscored"


def test_style_pins_match_current_versions() -> None:
    for name in ("style_fail", "style_pass"):
        pin = _pin(name)
        assert pin["rubric_version"] == rubric.RUBRIC_VERSION
        from pipeline.prompts import prompt_version

        assert pin["prompt_version"] == prompt_version("aesthetic_qc")
