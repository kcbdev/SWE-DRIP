"""One-shot research runner contracts (PBI-058) — offline, fakes + MemorySaver."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from api.app.collections_store import CollectionExists, CollectionNotFound, CollectionsStore
from api.app.inspiration import InspirationStore
from pipeline.collection_graph import RESEARCH_RUN_PREFIX
from pipeline.research_cli import DEMO_SLUG, main, run_once, seed_demo
from pipeline.runlog import MemoryRunLogger


def _png_bytes(width: int = 256, height: int = 256) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr
            + b"\x00" * 4 + b"\x00\x00\x00\x00IEND")


GOOD_DIRECTIVES = {
    "style_descriptors": ["mono-line", "flat fills"],
    "motifs": ["git branches", "conflict markers"],
    "palette_justification": "terminal greens on void black",
    "avoid": ["photorealism"],
}


class _Reply:
    def __init__(self, content: Any) -> None:
        self.content = content
        self.raw: dict[str, Any] = {"usage": {"prompt_tokens": 3, "completion_tokens": 7}}


class _StubClient:
    def chat(self, **kwargs: Any) -> _Reply:
        return _Reply(json.dumps(GOOD_DIRECTIVES))

    def image(self, **kwargs: Any) -> _Reply:
        return _Reply(_png_bytes())


class _FakeEngine:
    class _Conn:
        def __init__(self, outer: "_FakeEngine") -> None:
            self._outer = outer

        def execute(self, stmt: Any) -> None:
            self._outer.rows.append(1)

        def __enter__(self) -> "_FakeEngine._Conn":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    def __init__(self) -> None:
        self.rows: list[int] = []

    def begin(self) -> "_FakeEngine._Conn":
        return self._Conn(self)


def _seed_root(tmp_path: Path, monkeypatch) -> Path:
    import pipeline.paths as paths

    root = tmp_path / "collections"
    monkeypatch.setenv(paths.COLLECTIONS_DIR_ENV, str(root))
    root.mkdir(parents=True, exist_ok=True)
    (root / "styles.yaml").write_text(
        "version: 1\nstyles:\n"
        "  - name: mono-log\n    graphic_definition: Lines.\n",
        encoding="utf-8",
    )
    return root


def _draft(store: CollectionsStore) -> None:
    store.create({
        "collection_id": "vibe", "theme": "Vibe", "status": "draft",
        "style_archetype": "mono-log",
        "illustration_rules": {"line_weight": None, "palette": ["#0D0D0D"],
                               "no_mixed_styles": True},
        "garment_colorways": [], "placement_templates": [],
        "product_count_target": None, "lifecycle_days": None,
        "kpi_thresholds": {"min_units": None, "min_conversion": None,
                           "eval_window_days": None},
        "created_by": "u-9", "created_at": "2026-09-16T00:00:00+00:00",
        "approved_at": None, "retired_at": None, "survivor_products": [],
    })
    InspirationStore(store._root, store).add_link(
        "vibe", "https://example.com/board", "line quality")


class TestSeedDemo:
    def test_creates_valid_draft(self, tmp_path: Path, monkeypatch) -> None:
        root = _seed_root(tmp_path, monkeypatch)
        contract = seed_demo(CollectionsStore(root))
        assert contract["collection_id"] == DEMO_SLUG
        assert contract["inspiration_refs"][0]["url"].startswith("https://")

    def test_refuses_overwrite(self, tmp_path: Path, monkeypatch) -> None:
        root = _seed_root(tmp_path, monkeypatch)
        seed_demo(CollectionsStore(root))
        try:
            seed_demo(CollectionsStore(root))
        except CollectionExists:
            return
        raise AssertionError("second seed must refuse")


class TestRunOnce:
    def test_pauses_at_gate_with_board_and_draft(self, tmp_path: Path, monkeypatch) -> None:
        _seed_root(tmp_path, monkeypatch)
        store = CollectionsStore(tmp_path / "collections")
        _draft(store)
        summary = run_once(
            slug="vibe",
            llm_client=_StubClient(),
            cost_engine=_FakeEngine(),
            run_logger=MemoryRunLogger(),
            saver=MemorySaver(),
            assets_dir=str(tmp_path / "assets"),
        )
        assert summary["run_id"].startswith(RESEARCH_RUN_PREFIX)
        assert summary["awaiting_approval"] is True
        assert summary["board"]["board_version"] == 1
        assert summary["board"]["width"] == 256
        assert summary["draft_collection_id"] == "vibe"
        assert isinstance(summary["diversity_flags"], list)
        assert summary["errors"] == []
        assert (tmp_path / "assets" / "board.png").is_file()

    def test_unknown_slug_raises(self, tmp_path: Path, monkeypatch) -> None:
        _seed_root(tmp_path, monkeypatch)
        try:
            run_once(
                slug="ghost",
                llm_client=_StubClient(),
                cost_engine=_FakeEngine(),
                run_logger=MemoryRunLogger(),
                saver=MemorySaver(),
                assets_dir=str(tmp_path / "assets"),
            )
        except CollectionNotFound:
            return
        raise AssertionError("unknown slug must raise")


class TestMain:
    def test_usage_error(self, capsys) -> None:
        assert main([]) == 2

    def test_unknown_slug_exit_2(self, tmp_path: Path, monkeypatch, capsys) -> None:
        _seed_root(tmp_path, monkeypatch)
        assert main(["ghost"]) == 2
        assert "unknown collection" in capsys.readouterr().err
