"""Lineage record + diversity flags (PBI-051, spec C6) — pure, offline."""

from __future__ import annotations

from pipeline.lineage import build_lineage, diversity_flags, format_avoid


def _contract(slug: str, **overrides) -> dict:
    base = {
        "collection_id": slug,
        "theme": slug,
        "status": "active",
        "style_archetype": "mono-log",
        "illustration_rules": {"line_weight": None, "palette": ["#0D0D0D", "#00FF41"],
                               "no_mixed_styles": True},
        "style_descriptors": ["mono-line", "flat fills"],
    }
    base.update(overrides)
    return base


class TestBuildLineage:
    def test_collects_archetypes_palettes_motifs(self) -> None:
        lineage = build_lineage([_contract("a"), _contract("b", style_archetype="glitch-signal")])
        assert lineage["archetypes"] == ["mono-log", "glitch-signal"]
        assert lineage["palettes"] == ["#0D0D0D", "#00FF41"]
        assert lineage["motifs"] == ["mono-line", "flat fills"]
        assert lineage["collections"] == ["a", "b"]

    def test_skips_malformed_entries(self) -> None:
        lineage = build_lineage([_contract("a"), None, "nope", {}])  # type: ignore[list-item]
        assert lineage["archetypes"] == ["mono-log"]

    def test_empty_lineage(self) -> None:
        assert build_lineage([]) == {"collections": [], "archetypes": [],
                                     "palettes": [], "motifs": []}


class TestFormatAvoid:
    def test_negative_context_lines(self) -> None:
        lines = format_avoid(build_lineage([_contract("a")]))
        assert any("mono-log" in line and "taken" in line for line in lines)
        assert any("#0D0D0D" in line for line in lines)

    def test_empty_lineage_no_lines(self) -> None:
        assert format_avoid(build_lineage([])) == []


class TestDiversityFlags:
    def test_distinct_candidate_clean(self) -> None:
        lineage = build_lineage([_contract("a")])
        candidate = _contract("b", style_archetype="glitch-signal",
                              illustration_rules={"line_weight": None, "palette": ["#FF0000"],
                                                  "no_mixed_styles": True},
                              style_descriptors=["pixel-sorting"])
        assert diversity_flags(candidate, lineage) == []

    def test_shared_archetype_alone_is_legitimate(self) -> None:
        lineage = build_lineage([_contract("a")])
        candidate = _contract("b",
                              illustration_rules={"line_weight": None, "palette": ["#FF0000"],
                                                  "no_mixed_styles": True},
                              style_descriptors=["halftone dots"])
        assert diversity_flags(candidate, lineage) == []

    def test_near_duplicate_flagged_with_reasons(self) -> None:
        lineage = build_lineage([_contract("a")])
        flags = diversity_flags(_contract("b"), lineage)
        assert len(flags) == 1
        assert "near-duplicate" in flags[0] and "mono-log" in flags[0]
        assert "palette overlap" in flags[0] and "motif overlap" in flags[0]

    def test_malformed_candidate_loud(self) -> None:
        assert diversity_flags("nope", build_lineage([])) != []  # type: ignore[arg-type]
