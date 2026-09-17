"""One-shot item-run CLI contracts (PBI-060) — offline validation paths only.

The heavy path reuses CheckpointerRunStarter verbatim (API-proven); these
tests pin the CLI's own logic: usage, brief/design-type validation, and the
demo-template ensure step.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from api.app.collections_store import CollectionNotFound, CollectionsStore
from pipeline.run_cli import (
    DEMO_BRIEFS,
    DEMO_TEMPLATE,
    ensure_demo_template,
    main,
    parse_briefs,
)


def _store(tmp_path: Path) -> CollectionsStore:
    return CollectionsStore(tmp_path / "collections")


def _draft(store: CollectionsStore, **over: Any) -> None:
    base: dict[str, Any] = {
        "collection_id": "live-review", "theme": "Live Review", "status": "draft",
        "style_archetype": "mono-log",
        "illustration_rules": {"line_weight": None, "palette": ["#0D0D0D"],
                               "no_mixed_styles": True},
        "garment_colorways": [], "placement_templates": [],
        "product_count_target": None, "lifecycle_days": None,
        "kpi_thresholds": {"min_units": None, "min_conversion": None,
                           "eval_window_days": None},
        "created_by": "ops-cli", "created_at": "2026-09-17T00:00:00+00:00",
        "approved_at": None, "retired_at": None, "survivor_products": [],
    }
    base.update(over)
    store.create(base)


class TestParseBriefs:
    def test_demo_set_is_valid(self) -> None:
        from api.app.runs import validate_briefs

        assert validate_briefs(parse_briefs(None, True)) == []

    def test_explicit_json(self) -> None:
        import json

        parsed = parse_briefs(json.dumps(DEMO_BRIEFS), False)
        assert parsed is not None and parsed[0]["id"] == "live-1"

    def test_no_briefs_no_demo_is_none(self) -> None:
        assert parse_briefs(None, False) is None

    def test_malformed_json_loud(self) -> None:
        with pytest.raises(ValueError, match="JSON list"):
            parse_briefs("{nope", False)
        with pytest.raises(ValueError, match="JSON list"):
            parse_briefs('{"id": "x"}', False)


class TestMainValidation:
    def test_usage(self, capsys) -> None:
        assert main([]) == 2
        assert main(["a", "b"]) == 2

    def test_bad_design_type(self, capsys) -> None:
        assert main(["vibe", "--design-type", "nope"]) == 2
        assert "hero-icon" in capsys.readouterr().err

    def test_bad_briefs(self, capsys) -> None:
        assert main(["vibe", "--briefs", "{bad"]) == 2
        assert main(["vibe", "--briefs", "[]"]) == 2

    def test_out_of_range_brief_refused(self, capsys) -> None:
        import json

        bad = json.dumps([{"id": "b", "engagement": 999, "novelty": 1, "specificity": 1}])
        assert main(["vibe", "--briefs", bad]) == 2
        assert "out of locked range" in capsys.readouterr().err

    def test_empty_briefs_refused(self, capsys) -> None:
        assert main(["vibe", "--briefs", "[]"]) == 2
        assert "at least one brief" in capsys.readouterr().err


class TestEnsureDemoTemplate:
    def test_adds_template(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _draft(store)
        assert ensure_demo_template(store) is True
        templates = store.get("live-review")["contract"]["placement_templates"]
        assert templates[0]["design_type"] == DEMO_TEMPLATE["design_type"]

    def test_noop_when_present(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        _draft(store, placement_templates=[dict(DEMO_TEMPLATE)])
        assert ensure_demo_template(store) is False
        assert len(store.get("live-review")["contract"]["placement_templates"]) == 1

    def test_missing_draft_raises(self, tmp_path: Path) -> None:
        with pytest.raises(CollectionNotFound):
            ensure_demo_template(_store(tmp_path))
