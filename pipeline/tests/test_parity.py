"""A4 parity checks (spec C7): harness shape validators + offline end-to-end."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

HARNESS_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "parity_harness.py"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "briefs_sample_a.json"


def _load_harness():
    spec = importlib.util.spec_from_file_location("parity_harness", HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["parity_harness"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness():
    return _load_harness()


def test_fixture_loads(harness) -> None:
    sample = harness.load_fixture(FIXTURE_PATH)
    assert len(sample["briefs"]) == 2 and sample["brief"]["subject"]


def test_offline_sample_reaches_parity(harness, tmp_path: Path) -> None:
    sample = harness.load_fixture(FIXTURE_PATH)
    engine = harness.MemoryCostEngine()
    fw = harness.MockFW()
    state = harness.run_sample(
        sample,
        llm_client=harness.OpenRouterClient(api_key="parity-test", transport=harness.mock_transport()),
        fw_client=fw,
        cost_engine=engine,
        run_dir=str(tmp_path),
        thread_id="parity-test",
    )
    assert state["visited"] == harness.NODE_ORDER  # locked order, single pass
    assert harness.check_parity(state) == []
    assert len(engine.rows) == 5  # trend, copy, spec, render, aesthetic_qc
    assert fw.payloads and fw.payloads[0]["state"] == "DRAFT"


def test_parity_catches_public_leak(harness, tmp_path: Path) -> None:
    sample = harness.load_fixture(FIXTURE_PATH)
    state = harness.run_sample(
        sample,
        llm_client=harness.OpenRouterClient(api_key="t", transport=harness.mock_transport()),
        fw_client=harness.MockFW(),
        cost_engine=harness.MemoryCostEngine(),
        run_dir=str(tmp_path),
        thread_id="parity-leak",
    )
    state["publish_decision"] = {"approved": True, "state": "PUBLIC"}
    assert any("PUBLIC" in e for e in harness.check_parity(state))


def test_parity_catches_price_drift(harness, tmp_path: Path) -> None:
    sample = harness.load_fixture(FIXTURE_PATH)
    state = harness.run_sample(
        sample,
        llm_client=harness.OpenRouterClient(api_key="t", transport=harness.mock_transport()),
        fw_client=harness.MockFW(),
        cost_engine=harness.MemoryCostEngine(),
        run_dir=str(tmp_path),
        thread_id="parity-price",
    )
    state["fw_product"] = {**state["fw_product"], "price": 10.0}
    assert any("invariant" in e for e in harness.check_parity(state))


def test_parity_catches_broken_contract(harness) -> None:
    assert harness.check_parity({"collection_contract": {"status": "live"}}) != []


def test_live_mode_guards_missing_env(harness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert harness.main(["--live", "--fixture", str(FIXTURE_PATH)]) == 2


def test_harness_cli_exits_zero_offline(harness, tmp_path: Path, capsys) -> None:
    code = harness.main(["--fixture", str(FIXTURE_PATH)])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is True and report["errors"] == []
