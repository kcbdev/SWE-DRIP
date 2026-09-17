"""Styles management API contracts (PBI-056, spec C1) — offline, tmp dir + fakes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.audit import get_audit_writer
from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.collections_store import CollectionsStore, get_collections_store
from api.app.routers import styles as styles_router
from api.app.styles_store import (
    DuplicateStyle,
    RepoMissing,
    StylesStore,
    UnknownStyle,
    VersionConflict,
    get_styles_store,
)

SEED_STYLES = [
    {"name": "mono-log", "graphic_definition": "Single-weight terminal linework."},
    {"name": "halftone-zine", "graphic_definition": "Photocopy halftone collage."},
]


def _seed(root: Path, styles: list[dict[str, Any]] | None = None, version: int = 1) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "styles.yaml", "w", encoding="utf-8") as handle:
        yaml.safe_dump({"version": version, "styles": styles if styles is not None else SEED_STYLES},
                       handle, sort_keys=False, allow_unicode=True)
    return root


def _collections(tmp_path: Path) -> CollectionsStore:
    store = CollectionsStore(tmp_path / "collections")
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
    return store


class _NoopAudit:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.rows.append(kwargs)


def _client(role: str, styles: StylesStore, collections: CollectionsStore) -> tuple[TestClient, _NoopAudit]:
    audit = _NoopAudit()
    app = FastAPI()
    app.include_router(styles_router.router)
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", role)
    app.dependency_overrides[get_audit_writer] = lambda: audit
    app.dependency_overrides[get_styles_store] = lambda: styles
    app.dependency_overrides[get_collections_store] = lambda: collections
    return TestClient(app, raise_server_exceptions=False), audit


class TestList:
    def test_shape(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_VIEWER, StylesStore(root), _collections(tmp_path))
        body = client.get("/api/styles").json()
        assert body["version"] == 1
        assert [s["name"] for s in body["styles"]] == ["mono-log", "halftone-zine"]

    def test_missing_repo_503(self, tmp_path: Path) -> None:
        client, _ = _client(ROLE_VIEWER, StylesStore(tmp_path / "empty"), _collections(tmp_path))
        resp = client.get("/api/styles")
        assert resp.status_code == 503
        assert "styles.yaml" in resp.json()["detail"]

    def test_viewer_reads(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_VIEWER, StylesStore(root), _collections(tmp_path))
        assert client.get("/api/styles").status_code == 200


class TestCreate:
    def test_create_bumps_version_and_audits(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, audit = _client(ROLE_ADMIN, StylesStore(root), _collections(tmp_path))
        body = client.post("/api/styles", json={
            "name": "glitch-signal", "graphic_definition": "Analog glitch bars.",
            "expected_version": 1}).json()
        assert body["version"] == 2
        assert "glitch-signal" in [s["name"] for s in body["styles"]]
        assert body["affected_contracts"] == []
        assert audit.rows and audit.rows[0]["action"] == "styles.create"
        # the loader reads back what the API wrote (round-trip invariant)
        from pipeline.styles import load_file

        assert "glitch-signal" in [s["name"] for s in load_file(root / "styles.yaml")["styles"]]

    def test_duplicate_409(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_ADMIN, StylesStore(root), _collections(tmp_path))
        resp = client.post("/api/styles", json={
            "name": "mono-log", "graphic_definition": "Other.", "expected_version": 1})
        assert resp.status_code == 409

    def test_stale_version_409(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_ADMIN, StylesStore(root), _collections(tmp_path))
        resp = client.post("/api/styles", json={
            "name": "glitch-signal", "graphic_definition": "Analog glitch bars.",
            "expected_version": 99})
        assert resp.status_code == 409

    def test_empty_name_422(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_ADMIN, StylesStore(root), _collections(tmp_path))
        resp = client.post("/api/styles", json={
            "name": "  ", "graphic_definition": "x", "expected_version": 1})
        assert resp.status_code == 422

    def test_viewer_forbidden(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_VIEWER, StylesStore(root), _collections(tmp_path))
        assert client.post("/api/styles", json={
            "name": "x", "graphic_definition": "y", "expected_version": 1}).status_code == 403

    def test_missing_repo_503(self, tmp_path: Path) -> None:
        client, _ = _client(ROLE_ADMIN, StylesStore(tmp_path / "empty"), _collections(tmp_path))
        assert client.post("/api/styles", json={
            "name": "x", "graphic_definition": "y", "expected_version": 1}).status_code == 503


class TestUpdate:
    def test_rename_reports_stranded_contract(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, audit = _client(ROLE_ADMIN, StylesStore(root), _collections(tmp_path))
        body = client.patch("/api/styles/mono-log", json={
            "name": "mono-log-v2", "expected_version": 1}).json()
        assert body["version"] == 2
        # vibe still carries mono-log → reported, never silent
        assert body["affected_contracts"] == ["vibe"]
        assert audit.rows and audit.rows[0]["action"] == "styles.update"

    def test_redefine_keeps_name(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_ADMIN, StylesStore(root), _collections(tmp_path))
        body = client.patch("/api/styles/mono-log", json={
            "graphic_definition": "New words.", "expected_version": 1}).json()
        assert body["version"] == 2
        assert body["affected_contracts"] == []

    def test_unknown_404(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_ADMIN, StylesStore(root), _collections(tmp_path))
        assert client.patch("/api/styles/nope", json={"expected_version": 1}).status_code == 404

    def test_rename_collision_409(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_ADMIN, StylesStore(root), _collections(tmp_path))
        resp = client.patch("/api/styles/mono-log", json={
            "name": "halftone-zine", "expected_version": 1})
        assert resp.status_code == 409

    def test_viewer_forbidden(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_VIEWER, StylesStore(root), _collections(tmp_path))
        assert client.patch("/api/styles/mono-log", json={"expected_version": 1}).status_code == 403

    def test_noop_update_422(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_ADMIN, StylesStore(root), _collections(tmp_path))
        assert client.patch("/api/styles/mono-log", json={"expected_version": 1}).status_code == 422


class TestDelete:
    def test_delete_405_even_for_admin(self, tmp_path: Path) -> None:
        root = _seed(tmp_path / "collections")
        client, _ = _client(ROLE_ADMIN, StylesStore(root), _collections(tmp_path))
        resp = client.delete("/api/styles/mono-log")
        assert resp.status_code == 405
        assert "only grows" in resp.json()["detail"]


class TestStoreUnits:
    def test_store_errors(self, tmp_path: Path) -> None:
        store = StylesStore(tmp_path / "empty")
        with pytest.raises(RepoMissing):
            store.read()
        root = _seed(tmp_path / "collections")
        store = StylesStore(root)
        with pytest.raises(DuplicateStyle):
            store.create("mono-log", "Other.", 1)
        with pytest.raises(VersionConflict):
            store.create("new", "Def.", 99)
        with pytest.raises(UnknownStyle):
            store.update("ghost", "x", None, 1)

    def test_revalidate_lists_offenders(self) -> None:
        contracts = [{"collection_id": "a", "style_archetype": "mono-log"},
                     {"collection_id": "b", "style_archetype": "gone"}]
        assert StylesStore.revalidate(contracts, ["mono-log"]) == ["b"]
        assert StylesStore.revalidate(contracts, ["mono-log", "gone"]) == []
