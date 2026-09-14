"""Spike harness offline contract: --dry-run exits 0 with a full matrix."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SPIKE_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "fw_create_spike.py"


def _load():
    spec = importlib.util.spec_from_file_location("fw_create_spike", SPIKE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["fw_create_spike"] = module
    spec.loader.exec_module(module)
    return module


def test_dry_run_exits_zero_with_full_mocked_coverage() -> None:
    spike = _load()
    assert spike.main(["--dry-run"]) == 0


def test_coverage_of_detects_dropped_fields() -> None:
    spike = _load()
    case = {"design_type": "hero-icon", "front": "chest", "back": "none",
            "sleeve": "small-mark", "colorways": ["black"]}
    full = spike.coverage_of(case, {"placement": {"design_type": "hero-icon", "front": "chest",
                                    "back": "none", "sleeve": "small-mark"}, "colorways": ["black"]})
    assert full["full_coverage"] is True
    dropped = spike.coverage_of(case, {"placement": {"design_type": "hero-icon", "front": "chest",
                                       "back": "none", "sleeve": "none"}, "colorways": ["black"]})
    assert dropped["full_coverage"] is False
    assert dropped["kept"]["sleeve"] is False


def test_draft_payloads_are_never_published() -> None:
    spike = _load()
    for case in spike.MATRIX:
        assert spike.build_draft_payload(case)["state"] == "DRAFT"
