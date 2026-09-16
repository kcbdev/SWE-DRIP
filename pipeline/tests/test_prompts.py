"""Prompt overrides + effective prompt version (PBI-039, spec C4).

The built-in builders are the reviewed baseline: with no override the nodes
must send byte-identical prompts to today. An override replaces the prompt
verbatim, and the QC verdict's ``prompt_version`` changes with it — so
calibration compares like with like or flags the mismatch explicitly.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import pytest

from api.app.designs import calibration_for, design_detail_from_state
from pipeline import prompts
from pipeline import rubric
from pipeline.nodes.aesthetic_qc import aesthetic_qc
from pipeline.nodes.copy import listing_copy
from pipeline.nodes.trend import cluster_briefs, trend_research


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _ChatStub:
    """Minimal chat client: records calls, replays canned content."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.raw: dict[str, Any] = {"usage": {}}
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> "_ChatStub":
        self.calls.append(kwargs)
        return self

    def vision(self, **kwargs: Any) -> "_ChatStub":
        self.calls.append(kwargs)
        return self


def _png_bytes() -> bytes:
    ihdr = struct.pack(">IIBBBBB", 64, 64, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4


BRIEFS = [
    {"id": "b1", "subject": "Vibe Coding", "text": "tee about vibe coding",
     "style": "mono-log", "engagement": 35, "novelty": 20, "specificity": 15},
    {"id": "b2", "subject": "Merge Conflicts", "text": "tee about merge pain",
     "style": "mono-log", "engagement": 30, "novelty": 25, "specificity": 20},
]

GOOD_COPY = {
    "slogan": "Ship It Live",
    "title": "Vibe Coding Tee",
    "description": "A dry joke for developers who review diffs.",
    "tags": ["vibe-coding", "developer-tee"],
}

GOOD_SCORES = {"style_cohesion": 88, "focal_point": 92, "placement_fit": 85,
               "contrast": 90, "notes": "clean"}


def _cluster_reply() -> str:
    return json.dumps({"clusters": [{"theme": "Vibe", "brief_ids": ["b1", "b2"]}]})


# ---------------------------------------------------------------------------
# Registry: stable keys, loud on unknown nodes
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_prompt_keys_are_stable(self) -> None:
        assert prompts.prompt_key("trend_research") == "trend_clustering"
        assert prompts.prompt_key("listing_copy") == "listing_copy"
        assert prompts.prompt_key("design_spec") == "design_spec_rcao"
        assert prompts.prompt_key("aesthetic_qc") == "qc_rubric"

    def test_unknown_node_is_loud(self) -> None:
        with pytest.raises(KeyError):
            prompts.prompt_key("nope")
        with pytest.raises(KeyError):
            prompts.prompt_version("nope")
        with pytest.raises(KeyError):
            prompts.effective_prompt("nope", "built-in", None)

    def test_effective_prompt_semantics(self) -> None:
        assert prompts.effective_prompt("listing_copy", "built-in", None) == "built-in"
        assert prompts.effective_prompt("listing_copy", "built-in", "   ") == "built-in"
        assert prompts.effective_prompt("listing_copy", "built-in", "override") == "override"


# ---------------------------------------------------------------------------
# No override → identical prompt to today
# ---------------------------------------------------------------------------

class TestBuiltinPromptsUnchanged:
    def test_trend_builder_matches_todays_text(self) -> None:
        prompt = prompts.build_trend_prompt(BRIEFS)
        assert "thematic clusters" in prompt
        assert "id=b1" in prompt and "id=b2" in prompt

    def test_copy_builder_matches_todays_text(self) -> None:
        prompt = prompts.build_copy_prompt(BRIEFS[0])
        assert "dry developer-identity brand voice" in prompt
        assert "Vibe Coding" in prompt

    def test_spec_builder_matches_todays_text(self) -> None:
        prompt = prompts.build_spec_prompt(BRIEFS[0], {"theme": "Vibe", "style_archetype": "mono-log"})
        assert "RCAO framework" in prompt
        assert "mono-log" in prompt

    def test_qc_builder_matches_todays_text(self) -> None:
        prompt = prompts.build_qc_prompt(design_subject="x", style="y", attempt=1)
        assert "five-criterion" in prompt
        for criterion in rubric.CRITERIA:
            assert criterion in prompt

    def test_rubric_alias_still_resolves(self) -> None:
        assert rubric.build_qc_prompt is prompts.build_qc_prompt

    def test_node_sends_builtin_when_no_override(self) -> None:
        stub = _ChatStub(_cluster_reply())
        cluster_briefs(BRIEFS, stub, "m", {}, None)
        sent = stub.calls[0]["messages"][0]["content"]
        assert sent == prompts.build_trend_prompt(BRIEFS)


# ---------------------------------------------------------------------------
# Override replaces the prompt; version tracks it
# ---------------------------------------------------------------------------

class TestOverrides:
    def test_trend_override_replaces_prompt(self) -> None:
        stub = _ChatStub(_cluster_reply())
        override = "Cluster strictly by garment color, ignore theme."
        cluster_briefs(BRIEFS, stub, "m", {}, override)
        assert stub.calls[0]["messages"][0]["content"] == override

    def test_copy_node_override_replaces_prompt(self) -> None:
        stub = _ChatStub(json.dumps(GOOD_COPY))
        override = "Write copy like a pirate, matey."
        out = listing_copy(
            {"brief": dict(BRIEFS[0])},  # type: ignore[dict-item]
            {"configurable": {"llm_client": stub,
                              "node_config": {"listing_copy": {"prompt_override": override}}}},  # type: ignore[typeddict-item]
        )
        assert stub.calls[0]["messages"][0]["content"] == override
        assert out["listing_copy"]["slogan"] == "Ship It Live"

    def test_version_stable_without_override(self) -> None:
        assert prompts.prompt_version("aesthetic_qc") == prompts.prompt_version("aesthetic_qc")
        assert prompts.prompt_version("trend_research") == prompts.prompt_version("trend_research")

    def test_version_changes_with_override(self) -> None:
        base = prompts.prompt_version("aesthetic_qc")
        assert prompts.prompt_version("aesthetic_qc", "Score it harshly.") != base
        assert prompts.prompt_version("aesthetic_qc", "Score it harshly.") == \
            prompts.prompt_version("aesthetic_qc", "Score it harshly.")
        assert prompts.prompt_version("aesthetic_qc", "Score it kindly.") != \
            prompts.prompt_version("aesthetic_qc", "Score it harshly.")


# ---------------------------------------------------------------------------
# QC verdict carries prompt_version; prompt text never travels
# ---------------------------------------------------------------------------

def _qc_state(tmp_path: Path) -> dict[str, Any]:
    artifact = tmp_path / "render.png"
    artifact.write_bytes(_png_bytes())
    return {
        "design_id": "prompt-test",
        "brief": {"subject": "Rocket", "text": "x", "style": "mono-log"},
        "render_result": {"file_url": str(artifact)},
    }


class TestQcVerdictVersion:
    def test_verdict_carries_base_version_without_override(self, tmp_path: Path) -> None:
        stub = _ChatStub(json.dumps(GOOD_SCORES))
        out = aesthetic_qc(
            _qc_state(tmp_path),  # type: ignore[arg-type]
            {"configurable": {"llm_client": stub}},  # type: ignore[typeddict-item]
        )
        verdict = out["aesthetic_qc"]
        assert verdict["result"] == "pass"
        assert verdict["prompt_version"] == prompts.prompt_version("aesthetic_qc")
        assert verdict["prompt_key"] == "qc_rubric"
        assert verdict["rubric_version"] == rubric.RUBRIC_VERSION

    def test_verdict_version_changes_with_override(self, tmp_path: Path) -> None:
        stub = _ChatStub(json.dumps(GOOD_SCORES))
        override = "Score harshly XYZ-marker."
        out = aesthetic_qc(
            _qc_state(tmp_path),  # type: ignore[arg-type]
            {"configurable": {"llm_client": stub, "node_config": {
                "aesthetic_qc": {"prompt_override": override}}}},  # type: ignore[typeddict-item]
        )
        verdict = out["aesthetic_qc"]
        assert verdict["prompt_version"] == prompts.prompt_version("aesthetic_qc", override)
        assert verdict["prompt_version"] != prompts.prompt_version("aesthetic_qc")
        # The prompt text itself must not travel in the verdict (secrets backstop).
        assert "XYZ-marker" not in json.dumps(verdict)


# ---------------------------------------------------------------------------
# Calibration compares like with like — or says so
# ---------------------------------------------------------------------------

def _detail_with_qc(prompt_ver: str | None) -> dict[str, Any]:
    qc: dict[str, Any] = {"result": "pass",
                          "scores": {"style_cohesion": 88, "focal_point": 92,
                                     "placement_fit": 85, "contrast": 90},
                          "failing": [], "attempts": 1, "model_used": "m",
                          "rubric_version": 1, "prompt_key": "qc_rubric"}
    if prompt_ver is not None:
        qc["prompt_version"] = prompt_ver
    return design_detail_from_state({
        "design_id": "d-1", "run_id": "run-1", "aesthetic_qc": qc,
        "render_result": {"file_url": "runs/d-1/render.png"},
    }, "run-1")


def _approved() -> dict[str, Any]:
    return {"id": 1, "node": "aesthetic_qc", "status": "approved",
            "reviewer_user_id": "u-9", "note": None, "decided_at": "2026-09-16T00:00:00+00:00"}


class TestCalibrationVersionGuard:
    def test_matching_version_reports_agreement(self) -> None:
        joined = calibration_for(
            _detail_with_qc(prompts.prompt_version("aesthetic_qc")), [_approved()])
        assert joined["agreement"] is True
        assert joined["rubric"]["prompt_version"] == prompts.prompt_version("aesthetic_qc")

    def test_mismatched_version_flags_unknown_not_agreement(self) -> None:
        joined = calibration_for(_detail_with_qc("000000000000"), [_approved()])
        assert joined["agreement"] is None
        assert "prompt changed" in (joined["note"] or "")

    def test_unversioned_verdict_treated_as_builtin(self) -> None:
        # Runs recorded before versioning used the built-in prompt by construction.
        joined = calibration_for(_detail_with_qc(None), [_approved()])
        assert joined["agreement"] is True

    def test_pins_match_current_prompt_version(self) -> None:
        import json as _json

        fixtures = Path(__file__).parent / "fixtures" / "qc"
        for name in ("ninja", "rocket"):
            pin = _json.loads((fixtures / f"{name}.json").read_text(encoding="utf-8"))
            assert pin["prompt_version"] == prompts.prompt_version("aesthetic_qc")


# ---------------------------------------------------------------------------
# Secrets never logged
# ---------------------------------------------------------------------------

class TestSecretRedaction:
    def test_openrouter_key_masked(self) -> None:
        candidate = "sk" + "-or-" + "testkey123abc"
        redacted = prompts.redact_for_log(f"use key {candidate} now")
        assert "testkey123abc" not in redacted
        assert "[REDACTED-OPENROUTER-KEY]" in redacted

    def test_assignment_and_bearer_masked(self) -> None:
        redacted = prompts.redact_for_log("api_key=supersecret123 and Bearer abcDEF123")
        assert "supersecret123" not in redacted
        assert "abcDEF123" not in redacted

    def test_non_strings_pass_through(self) -> None:
        assert prompts.redact_for_log(None) is None
        assert prompts.redact_for_log(42) == 42
