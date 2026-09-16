"""Collection-research graph contracts (PBI-050, spec C4) — offline, fakes."""

from __future__ import annotations

import base64
import json
import struct
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver

from pipeline.collection_graph import (
    RESEARCH_DEFAULT_HITL,
    RESEARCH_ORDER,
    build_collection_graph,
    register_research_node,
)
from pipeline.nodes.research_board import art_render_board, build_board_prompt
from pipeline.nodes.research_synthesis import (
    build_synthesis_prompt,
    prompt_fingerprint,
)
from pipeline.runlog import MemoryRunLogger


def _png_bytes(width: int = 256, height: int = 256) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4 + b"\x00\x00\x00\x00IEND"


class _Reply:
    def __init__(self, content: Any) -> None:
        self.content = content
        self.raw: dict[str, Any] = {"usage": {"prompt_tokens": 3, "completion_tokens": 7}}


class _StubClient:
    def __init__(self, chat_content: str = "", image_bytes: bytes | None = None,
                 fail_image_once: bool = False) -> None:
        self._chat_content = chat_content
        self._image_bytes = image_bytes if image_bytes is not None else _png_bytes()
        self._fail_image_once = fail_image_once
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> _Reply:
        self.calls.append({"kind": "chat", **kwargs})
        return _Reply(self._chat_content)

    def image(self, **kwargs: Any) -> _Reply:
        self.calls.append({"kind": "image", **kwargs})
        if self._fail_image_once:
            self._fail_image_once = False
            raise RuntimeError("primary refused")
        return _Reply(self._image_bytes)


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


GOOD_DIRECTIVES = {
    "style_descriptors": ["mono-line", "flat fills"],
    "motifs": ["git branches", "conflict markers"],
    "palette_justification": "terminal greens on void black",
    "avoid": ["photorealism"],
}

INSPIRATION = {
    "assets": [{"id": "a1", "filename": "a1.png"}],
    "refs": [{"url": "https://example.com/board", "note": "line quality"}],
}


def _config(tmp_path: Path, **extra: Any) -> dict[str, Any]:
    return {"configurable": {
        "llm_client": extra.pop("client"),
        "cost_engine": extra.pop("engine", None) or _FakeEngine(),
        "run_logger": extra.pop("logger", None) or MemoryRunLogger(),
        "thread_id": "research-1",
        "research_assets_dir": str(tmp_path / "assets"),
        "hitl": {"inspiration_review": False, "style_synthesis": False,
                 "mood_board": False, "contract_draft": False,
                 "collection_gate": False},
        **extra,
    }}


class TestRegistry:
    def test_locked_order(self) -> None:
        assert RESEARCH_ORDER == ["inspiration_review", "style_synthesis", "mood_board",
                                  "contract_draft", "collection_gate"]

    def test_register_rejects_unknown(self) -> None:
        with pytest.raises(KeyError):
            register_research_node("nope", lambda s, c=None: {})

    def test_gate_defaults_on(self) -> None:
        assert RESEARCH_DEFAULT_HITL["collection_gate"] is True

    def test_every_node_registered_not_placeholder(self) -> None:
        """A missing register_* call silently installs a placeholder that
        returns visited-only — this test makes that failure loud."""
        from pipeline import collection_graph as graph_module

        build_collection_graph()
        assert set(graph_module._RESEARCH_IMPLS) == set(RESEARCH_ORDER)


class TestReview:
    def test_empty_inspiration_is_loud(self, tmp_path: Path) -> None:
        from pipeline.nodes.research_review import inspiration_review

        out = inspiration_review(
            {"collection_slug": "x"},  # type: ignore[dict-item]
            _config(tmp_path, client=_StubClient()),  # type: ignore[typeddict-item]
        )
        assert out["errors"] and "no inspiration" in out["errors"][0]

    def test_inventory_recorded(self, tmp_path: Path) -> None:
        from pipeline.nodes.research_review import inspiration_review

        out = inspiration_review(
            {"collection_slug": "x", "inspiration": dict(INSPIRATION)},  # type: ignore[dict-item]
            _config(tmp_path, client=_StubClient()),  # type: ignore[typeddict-item]
        )
        assert out["inspiration"]["reviewed"] == {"asset_count": 1, "ref_count": 1}


class TestSynthesis:
    def test_builder_marks_vocab_refs_and_avoid(self) -> None:
        prompt = build_synthesis_prompt(dict(INSPIRATION), ["glitch-signal"], ["mono-log"])
        assert "mono-log" in prompt
        assert "https://example.com/board" in prompt
        assert "glitch-signal" in prompt
        assert "Do not invent product copy" in prompt

    def test_fingerprint_stable_per_input(self) -> None:
        assert prompt_fingerprint("abc") == prompt_fingerprint("abc")
        assert prompt_fingerprint("abc") != prompt_fingerprint("abd")

    def test_override_model_wins(self, tmp_path: Path) -> None:
        from pipeline.nodes.research_synthesis import style_synthesis

        stub = _StubClient(json.dumps(GOOD_DIRECTIVES))
        out = style_synthesis(
            {"inspiration": dict(INSPIRATION)},  # type: ignore[dict-item]
            _config(tmp_path, client=stub,  # type: ignore[typeddict-item]
                    research_models={"style_synthesis": "custom/model"}),
        )
        assert stub.calls[0]["model"] == "custom/model"
        assert out["synthesis"]["model_used"] == "custom/model"
        assert len(out["synthesis"]["prompt_version"]) == 12

    def test_bad_json_is_loud(self, tmp_path: Path) -> None:
        from pipeline.nodes.research_synthesis import style_synthesis

        with pytest.raises(ValueError, match="did not return JSON"):
            style_synthesis(
                {"inspiration": dict(INSPIRATION)},  # type: ignore[dict-item]
                _config(tmp_path, client=_StubClient("not json")),  # type: ignore[typeddict-item]
            )

    def test_missing_descriptors_is_loud(self, tmp_path: Path) -> None:
        from pipeline.nodes.research_synthesis import style_synthesis

        with pytest.raises(ValueError, match="no style_descriptors"):
            style_synthesis(
                {"inspiration": dict(INSPIRATION)},  # type: ignore[dict-item]
                _config(tmp_path,  # type: ignore[typeddict-item]
                        client=_StubClient(json.dumps({"motifs": []}))),
            )


class TestBoard:
    def test_builder_names_directives_and_avoid(self) -> None:
        prompt = build_board_prompt(GOOD_DIRECTIVES)
        assert "mono-line" in prompt and "NOT a product" in prompt
        assert "photorealism" in prompt

    def test_fallback_tried_in_order(self) -> None:
        stub = _StubClient(fail_image_once=True)
        result, used = art_render_board("p", stub, ["m-1", "m-2"])
        assert used == "m-2"
        assert [c["model"] for c in stub.calls] == ["m-1", "m-2"]

    def test_all_failing_is_loud(self) -> None:
        class AlwaysBoom:
            def image(self, **kwargs: Any) -> Any:
                raise RuntimeError("nope")

        with pytest.raises(RuntimeError, match="all image models failed"):
            art_render_board("p", AlwaysBoom(), ["m-1"])

    def test_render_persists_ref_and_bumps_version(self, tmp_path: Path) -> None:
        from pipeline.nodes.research_board import mood_board

        stub = _StubClient()
        out = mood_board(
            {"collection_slug": "vibe",  # type: ignore[dict-item]
             "synthesis": dict(GOOD_DIRECTIVES)},
            _config(tmp_path, client=stub),  # type: ignore[typeddict-item]
        )
        board = out["board"]
        assert Path(board["file_ref"]).is_file()
        assert board["board_version"] == 1
        assert board["width"] == 256

    def test_rerender_never_overwrites(self, tmp_path: Path) -> None:
        from pipeline.nodes.research_board import mood_board

        cfg = _config(tmp_path, client=_StubClient())
        state: dict[str, Any] = {"collection_slug": "vibe",
                                 "synthesis": dict(GOOD_DIRECTIVES)}
        first = mood_board(state, cfg)["board"]  # type: ignore[arg-type]
        second = mood_board({**state, "board": {"board_version": 1}}, cfg)["board"]  # type: ignore[arg-type]
        assert first["file_ref"] != second["file_ref"]
        assert second["board_version"] == 2

    def test_bad_payload_is_loud(self, tmp_path: Path) -> None:
        from pipeline.nodes.research_board import mood_board

        with pytest.raises(ValueError, match="unusable"):
            mood_board(
                {"collection_slug": "vibe",  # type: ignore[dict-item]
                 "synthesis": dict(GOOD_DIRECTIVES)},
                _config(tmp_path,  # type: ignore[typeddict-item]
                        client=_StubClient(image_bytes=b"not-an-image")),
            )


class TestDraft:
    def test_missing_style_is_recorded_not_defaulted(self, tmp_path: Path) -> None:
        from pipeline.nodes.research_draft import contract_draft

        out = contract_draft(
            {"inspiration": dict(INSPIRATION),  # type: ignore[dict-item]
             "synthesis": dict(GOOD_DIRECTIVES)},
            _config(tmp_path, client=_StubClient()),  # type: ignore[typeddict-item]
        )
        assert any("no style_archetype" in e for e in out["errors"])
        assert "draft_contract" not in out

    def test_absent_lineage_means_no_check(self, tmp_path: Path) -> None:
        from pipeline.nodes.research_draft import contract_draft

        out = contract_draft(
            {"collection_slug": "v", "collection_theme": "Vibe",  # type: ignore[dict-item]
             "style_archetype": "mono-log",
             "inspiration": dict(INSPIRATION), "synthesis": dict(GOOD_DIRECTIVES)},
            _config(tmp_path, client=_StubClient()),  # type: ignore[typeddict-item]
        )
        assert out["draft_contract"]["collection_id"] == "vibe"
        assert "diversity_flags" not in out

    def test_near_duplicate_flagged_not_silent(self, tmp_path: Path) -> None:
        from pipeline.lineage import build_lineage
        from pipeline.nodes.research_draft import contract_draft

        lineage = build_lineage([{
            "collection_id": "old", "style_archetype": "mono-log",
            "illustration_rules": {"palette": ["#0D0D0D"]},
            "style_descriptors": ["mono-line"],
        }])
        out = contract_draft(
            {"collection_slug": "v", "collection_theme": "Vibe",  # type: ignore[dict-item]
             "style_archetype": "mono-log",
             "inspiration": dict(INSPIRATION),
             "synthesis": {**GOOD_DIRECTIVES, "style_descriptors": ["mono-line"]},
             "lineage": lineage},
            _config(tmp_path, client=_StubClient()),  # type: ignore[typeddict-item]
        )
        # Empty draft palette + synthesis motif mono-line overlapping the
        # lineage motif → flagged (motif overlap alone suffices with a
        # shared archetype).
        assert any("near-duplicate" in f for f in out.get("diversity_flags", []))

    def test_draft_shape_valid_with_empty_unknowables(self, tmp_path: Path) -> None:
        from pipeline.nodes.contract import validate_contract
        from pipeline.nodes.research_draft import contract_draft

        out = contract_draft(
            {"collection_slug": "v", "collection_theme": "Vibe",  # type: ignore[dict-item]
             "style_archetype": "mono-log",
             "inspiration": dict(INSPIRATION), "synthesis": dict(GOOD_DIRECTIVES)},
            _config(tmp_path, client=_StubClient()),  # type: ignore[typeddict-item]
        )
        draft = out["draft_contract"]
        assert validate_contract(draft) == []
        assert draft["status"] == "draft"
        assert draft["illustration_rules"]["palette"] == []
        assert draft["created_by"] == "research-graph"


class TestGate:
    def test_gate_off_defaults_not_approved(self, tmp_path: Path) -> None:
        from pipeline.nodes.research_gate import collection_gate

        out = collection_gate(
            {"draft_contract": {"collection_id": "v"}},  # type: ignore[dict-item]
            _config(tmp_path, client=_StubClient()),  # type: ignore[typeddict-item]
        )
        assert out["gate_decision"] == {"approved": False, "draft_collection_id": "v",
                                        "board_version": None}

    def _run_to_gate(self, tmp_path: Path, thread: str):
        from langgraph.types import Command  # noqa: F401 (used by callers)

        graph = build_collection_graph(checkpointer=MemorySaver())
        cfg: dict[str, Any] = {"configurable": {
            "llm_client": _StubClient(json.dumps(GOOD_DIRECTIVES)),
            "cost_engine": _FakeEngine(), "run_logger": MemoryRunLogger(),
            "thread_id": thread, "research_assets_dir": str(tmp_path / "assets"),
            "hitl": {n: (n == "collection_gate") for n in RESEARCH_ORDER}}}
        out = graph.invoke(
            {"collection_slug": "vibe", "collection_theme": "Vibe",
             "style_archetype": "mono-log", "inspiration": dict(INSPIRATION),
             "avoid": []},
            cfg,
        )
        return graph, cfg, out

    def test_interrupt_carries_draft_and_board(self, tmp_path: Path) -> None:
        _, _, out = self._run_to_gate(tmp_path, "r-gate-1")
        (interrupt,) = out["__interrupt__"]
        assert interrupt.value["node"] == "collection_gate"
        assert interrupt.value["draft"]["collection_id"] == "vibe"
        assert interrupt.value["draft"]["status"] == "draft"
        assert interrupt.value["board"]["board_version"] == 1
        assert interrupt.value["diversity_flags"] == []

    def test_resume_approve_reject_and_edit(self, tmp_path: Path) -> None:
        from langgraph.types import Command

        graph, cfg, _ = self._run_to_gate(tmp_path, "r-gate-2")
        approved = graph.invoke(Command(resume={"approved": True, "note": "go"}), cfg)
        assert approved["gate_decision"]["approved"] is True

        graph2, cfg2, _ = self._run_to_gate(tmp_path, "r-gate-3")
        rejected = graph2.invoke(Command(resume={"approved": False}), cfg2)
        assert rejected["gate_decision"]["approved"] is False

        graph3, cfg3, _ = self._run_to_gate(tmp_path, "r-gate-4")
        edited = graph3.invoke(
            Command(resume={"approved": True,
                            "contract": {"theme": "Vibe Coding v2"}}), cfg3)
        decision = edited["gate_decision"]
        assert decision["approved"] is True
        assert decision["edited_contract"]["theme"] == "Vibe Coding v2"
        assert decision["edited_contract"]["collection_id"] == "vibe"
        assert decision["edited_contract"]["status"] == "draft"

    def test_resume_malformed_edit_is_loud(self, tmp_path: Path) -> None:
        from langgraph.types import Command

        graph, cfg, _ = self._run_to_gate(tmp_path, "r-gate-5")
        with pytest.raises(ValueError, match="edited contract is invalid"):
            graph.invoke(
                Command(resume={"approved": True,
                                "contract": {"style_archetype": ""}}), cfg)


class TestFullGraph:
    def test_locked_order_end_to_end_offline(self, tmp_path: Path) -> None:
        logger = MemoryRunLogger()
        engine = _FakeEngine()
        stub = _StubClient(json.dumps(GOOD_DIRECTIVES))
        graph = build_collection_graph(checkpointer=MemorySaver())
        out = graph.invoke(
            {"collection_slug": "vibe", "collection_theme": "Vibe",
             "style_archetype": "mono-log", "inspiration": dict(INSPIRATION),
             "avoid": []},
            {"configurable": {"llm_client": stub, "cost_engine": engine,
                              "run_logger": logger, "thread_id": "r-g",
                              "research_assets_dir": str(tmp_path / "assets"),
                              "hitl": {n: False for n in RESEARCH_ORDER}}},
        )
        assert out["visited"] == RESEARCH_ORDER
        assert out["draft_contract"]["collection_id"] == "vibe"
        assert out["gate_decision"]["approved"] is False
        assert len(engine.rows) == 2  # synthesis + board cost rows
        assert {r.node for r in logger.rows} >= {"style_synthesis", "mood_board"}
