"""Rotation queue endpoint (PBI-051, spec C6) — offline, tmp store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.collections_store import CollectionsStore, get_collections_store
from api.app.routers import collections as collections_router


def _draft(slug: str, theme: str = "T", created: str = "2026-09-16T00:00:00+00:00") -> dict[str, Any]:
    return {
        "collection_id": slug, "theme": theme, "status": "draft",
        "style_archetype": "mono-log",
        "illustration_rules": {"line_weight": None, "palette": ["#0D0D0D"],
                               "no_mixed_styles": True},
        "garment_colorways": [], "placement_templates": [],
        "product_count_target": None, "lifecycle_days": None,
        "kpi_thresholds": {"min_units": None, "min_conversion": None,
                           "eval_window_days": None},
        "created_by": "u-9", "created_at": created,
        "approved_at": None, "retired_at": None, "survivor_products": [],
    }


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    store = CollectionsStore(tmp_path / "collections")
    store.create(_draft("new", created="2026-09-16T02:00:00+00:00"))
    store.create(_draft("old", created="2026-09-16T01:00:00+00:00"))
    store.create({**_draft("live"), "status": "active"})
    app = FastAPI()
    app.include_router(collections_router.router)
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", ROLE_VIEWER)
    app.dependency_overrides[get_collections_store] = lambda: store
    return TestClient(app, raise_server_exceptions=False)


class TestRotation:
    def test_next_candidate_is_oldest_draft(self, client: TestClient) -> None:
        body = client.get("/api/collections/rotation").json()
        assert body["next_candidate"] == "old"
        assert body["drafts"] == 2
        assert body["actives"] == 1

    def test_no_drafts_is_null(self, tmp_path: Path) -> None:
        store = CollectionsStore(tmp_path / "c2")
        store.create({**_draft("solo"), "status": "active"})
        app = FastAPI()
        app.include_router(collections_router.router)
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", ROLE_VIEWER)
        app.dependency_overrides[get_collections_store] = lambda: store
        body = TestClient(app, raise_server_exceptions=False).get(
            "/api/collections/rotation").json()
        assert body["next_candidate"] is None
        assert body["actives"] == 1

    def test_rotation_not_captured_as_slug(self, client: TestClient) -> None:
        assert client.get("/api/collections/rotation").status_code == 200

    def test_viewer_can_read(self, client: TestClient) -> None:
        assert client.get("/api/collections/rotation").status_code == 200
