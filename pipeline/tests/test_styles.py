"""Style repository + contract v2 (PBI-048, spec C1/C2).

The 7 locked names live in collections/styles.yaml — agents and validators
read through pipeline/styles.py, nothing hardcodes them. Founder taste gate:
these names are PROPOSED until ratified; the tests pin the count and the
two continuity names (mono-log, terminal-brutalist) so a rename is loud.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from pipeline.styles import (
    assert_known_archetype,
    get_style,
    load_styles,
    style_names,
)


class TestRepo:
    def test_exactly_seven_locked_names(self) -> None:
        names = style_names()
        assert len(names) == 7
        assert len(set(names)) == 7

    def test_continuity_names_kept(self) -> None:
        # Live runs use mono-log; fixtures use terminal-brutalist — dropping
        # either would orphan real data, so the proposal keeps both.
        assert "mono-log" in style_names()
        assert "terminal-brutalist" in style_names()

    def test_definitions_are_graphic_not_vibes(self) -> None:
        for name in style_names():
            entry = get_style(name)
            assert len(entry["graphic_definition"]) >= 20
            assert "not" in entry

    def test_unknown_name_is_loud(self) -> None:
        with pytest.raises(KeyError):
            get_style("watercolor-dreams")
        with pytest.raises(ValueError):
            assert_known_archetype("watercolor-dreams")

    def test_known_name_passes_through(self) -> None:
        assert assert_known_archetype("mono-log") == "mono-log"

    def test_missing_file_is_loud(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            style_names(root=tmp_path / "empty")

    def test_duplicate_names_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "c"
        (root / "collections").mkdir(parents=True)
        (root / "collections" / "styles.yaml").write_text(
            yaml.safe_dump({"version": 1, "styles": [
                {"name": "x", "graphic_definition": "one"},
                {"name": "x", "graphic_definition": "two"},
            ]}), encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate"):
            style_names(root=root)

    def test_version_present(self) -> None:
        assert load_styles()["version"] == 1


class TestContractV2Keys:
    def test_v1_dict_without_v2_keys_validates_at_pipeline_layer(self) -> None:
        """validate_contract must accept pre-v2 dicts (finding: v2 keys optional)."""
        from pipeline.nodes.contract import validate_contract

        v1 = dict(_v1_base())
        for key in ("style_descriptors", "mood_board", "inspiration_refs",
                    "avoid", "board_version"):
            v1.pop(key, None)
        assert validate_contract(v1) == []

    def test_malformed_v2_values_rejected_at_pipeline_layer(self) -> None:
        from pipeline.nodes.contract import validate_contract

        bad = dict(_v1_base(), mood_board="not-a-list", board_version=0)
        errors = validate_contract(bad)
        assert any("mood_board" in e for e in errors)
        assert any("board_version" in e for e in errors)

    def test_draft_carries_empty_visual_placeholders(self) -> None:
        from pipeline.nodes.contract import draft_contract

        draft = draft_contract(
            {"cluster_id": "c-1", "theme": "T", "brief_ids": ["b-1"]},
            ["mono-log"],
        )
        assert draft["style_descriptors"] == []
        assert draft["mood_board"] == []
        assert draft["inspiration_refs"] == []
        assert draft["avoid"] == []
        assert draft["board_version"] == 1

    def test_v1_contract_validates_unchanged(self) -> None:
        from api.app.collections_schema import CollectionContract

        v1: dict[str, Any] = {
            "collection_id": "vibe-coding", "theme": "Vibe", "status": "draft",
            "style_archetype": "mono-log",
            "illustration_rules": {"line_weight": None, "palette": ["#0D0D0D"],
                                   "no_mixed_styles": True},
            "garment_colorways": [], "placement_templates": [],
            "product_count_target": None, "lifecycle_days": None,
            "kpi_thresholds": {"min_units": None, "min_conversion": None,
                               "eval_window_days": None},
            "created_by": "u-1", "created_at": "2026-09-16T00:00:00+00:00",
            "approved_at": None, "retired_at": None, "survivor_products": [],
        }
        contract = CollectionContract(**v1)
        assert contract.style_descriptors == []
        assert contract.board_version == 1

    def test_mood_board_rejects_urls_and_absolute_paths(self) -> None:
        from pydantic import ValidationError

        from api.app.collections_schema import CollectionContract

        base = _v1_base()
        for bad in ("https://example.com/board.png", "/etc/board.png", "  ",
                    "../board.png", "C:\\board.png", "data:image/png,xx",
                    "  /abs.png"):
            with pytest.raises(ValidationError):
                CollectionContract(**{**base, "mood_board": [bad]})

    def test_mood_board_accepts_relative_refs(self) -> None:
        from api.app.collections_schema import CollectionContract

        contract = CollectionContract(
            **{**_v1_base(), "mood_board": ["board/sheet-1.png"]})
        assert contract.mood_board == ["board/sheet-1.png"]


def _v1_base() -> dict[str, Any]:
    return {
        "collection_id": "vibe-coding", "theme": "Vibe", "status": "draft",
        "style_archetype": "mono-log",
        "illustration_rules": {"line_weight": None, "palette": ["#0D0D0D"],
                               "no_mixed_styles": True},
        "garment_colorways": [], "placement_templates": [],
        "product_count_target": None, "lifecycle_days": None,
        "kpi_thresholds": {"min_units": None, "min_conversion": None,
                           "eval_window_days": None},
        "created_by": "u-1", "created_at": "2026-09-16T00:00:00+00:00",
        "approved_at": None, "retired_at": None, "survivor_products": [],
    }
