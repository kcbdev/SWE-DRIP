"""Durable artifact roots (PBI-053, spec C3b).

Env resolution with repo-relative fallback, single-source delegation, and
a grep guard: no hardcoded `runs/` / `collections/` literals may remain on
the touched flows (`pipeline/paths.py` owns the only literals).
"""

from __future__ import annotations

from pathlib import Path

import pipeline.paths as paths


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def test_runs_root_defaults_repo_relative(monkeypatch) -> None:
    monkeypatch.delenv(paths.RUNS_DIR_ENV, raising=False)
    assert paths.runs_root() == _repo_root() / "runs"


def test_runs_root_honors_env(monkeypatch, tmp_path) -> None:
    target = tmp_path / "vol-runs"
    monkeypatch.setenv(paths.RUNS_DIR_ENV, str(target))
    assert paths.runs_root() == target


def test_collections_root_defaults_repo_relative(monkeypatch) -> None:
    monkeypatch.delenv(paths.COLLECTIONS_DIR_ENV, raising=False)
    assert paths.collections_root() == _repo_root() / "collections"


def test_collections_root_honors_env(monkeypatch, tmp_path) -> None:
    target = tmp_path / "vol-collections"
    monkeypatch.setenv(paths.COLLECTIONS_DIR_ENV, str(target))
    assert paths.collections_root() == target


def test_api_runs_root_delegates_to_single_source(monkeypatch, tmp_path) -> None:
    from api.app.runs import runs_root as api_runs_root

    target = tmp_path / "vol-runs"
    monkeypatch.setenv(paths.RUNS_DIR_ENV, str(target))
    assert api_runs_root() == paths.runs_root() == target


def test_designs_serving_root_follows_env(monkeypatch, tmp_path) -> None:
    from api.app.routers.designs import get_runs_root

    target = tmp_path / "vol-runs"
    monkeypatch.setenv(paths.RUNS_DIR_ENV, str(target))
    assert get_runs_root() == target


def test_prod_collections_store_uses_env_root(monkeypatch, tmp_path) -> None:
    from api.app.collections_store import get_collections_store

    target = tmp_path / "vol-collections"
    target.mkdir()
    monkeypatch.setenv(paths.COLLECTIONS_DIR_ENV, str(target))
    assert get_collections_store()._root == target


def test_styles_repo_follows_env_root(monkeypatch, tmp_path) -> None:
    from pipeline.styles import repo_path

    target = tmp_path / "vol-collections"
    monkeypatch.setenv(paths.COLLECTIONS_DIR_ENV, str(target))
    assert repo_path() == target / "styles.yaml"


def test_styles_repo_explicit_root_keeps_legacy_layout(tmp_path) -> None:
    from pipeline.styles import repo_path

    assert repo_path(tmp_path) == tmp_path / "collections" / "styles.yaml"


FLOW_FILES = [
    "api/app/runs.py",
    "api/app/routers/designs.py",
    "api/app/collections_store.py",
    "api/app/inspiration.py",
    "api/app/routers/inspiration.py",
    "pipeline/nodes/render.py",
    "pipeline/nodes/research_board.py",
    "pipeline/styles.py",
]


def test_no_hardcoded_artifact_roots() -> None:
    """Grep guard: path literals live in `pipeline/paths.py` only."""
    offenders: list[str] = []
    for rel in FLOW_FILES:
        full = _repo_root() / rel
        assert full.is_file(), f"guard file list drifted: {rel}"
        for lineno, line in enumerate(full.read_text(encoding="utf-8").splitlines(), 1):
            if "runs/" in line or "collections/" in line:
                offenders.append(f"{rel}:{lineno}:{line.strip()[:100]}")
    assert offenders == [], f"hardcoded artifact roots: {offenders!r}"
