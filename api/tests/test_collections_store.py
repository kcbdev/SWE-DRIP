"""Collections YAML store + CRUD API contracts (offline, tmp dir + fakes)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.app.auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor, get_current_actor
from api.app.audit import get_audit_writer
from api.app.collections_store import (
    CollectionExists,
    CollectionNotFound,
    CollectionsStore,
    MtimeConflict,
    get_collections_store,
)
from api.app.routers import collections as collections_router


def _draft(slug: str = "vibe-coding", **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "collection_id": slug,
        "theme": "Vibe Coding",
        "status": "draft",
        "style_archetype": "terminal-brutalist",
        "illustration_rules": {
            "line_weight": "bold",
            "palette": ["#0D0D0D", "#00FF41"],
            "no_mixed_styles": True,
        },
        "garment_colorways": [{"base": "black", "contrast_pass": True}],
        "placement_templates": [
            {"design_type": "hero-icon", "front": "chest", "back": "none", "sleeve": "none"}
        ],
        "product_count_target": 6,
        "lifecycle_days": 90,
        "kpi_thresholds": {"min_units": 5, "min_conversion": 0.02, "eval_window_days": 30},
        "created_by": "u-1",
        "created_at": "2026-09-14T10:00:00+00:00",
        "approved_at": None,
        "retired_at": None,
    }
    base.update(overrides)
    return base


@pytest.fixture()
def store(tmp_path: Path) -> CollectionsStore:
    return CollectionsStore(tmp_path / "collections")


# ------------------------------------------------------------------- store


def test_round_trip_read_write(store: CollectionsStore) -> None:
    created = store.create(_draft())
    assert created["contract"]["collection_id"] == "vibe-coding"
    assert created["mtime"] > 0
    fetched = store.get("vibe-coding")
    assert fetched["contract"] == created["contract"]
    updated = store.update("vibe-coding", {"theme": "Vibe Coding v2"})
    assert updated["contract"]["theme"] == "Vibe Coding v2"
    assert updated["contract"]["status"] == "draft"


def test_list_filter_by_status(store: CollectionsStore) -> None:
    store.create(_draft("a"))
    store.create(_draft("b", status="active"))
    assert {r["contract"]["collection_id"] for r in store.list()} == {"a", "b"}
    assert [r["contract"]["collection_id"] for r in store.list(status="active")] == ["b"]


def test_unknown_slug_is_not_found(store: CollectionsStore) -> None:
    with pytest.raises(CollectionNotFound):
        store.get("nope")


def test_slug_collision_is_an_error_not_overwrite(store: CollectionsStore) -> None:
    store.create(_draft())
    with pytest.raises(CollectionExists):
        store.create(_draft())
    assert store.get("vibe-coding")["contract"]["theme"] == "Vibe Coding"


def test_validation_rejects_missing_kpi_thresholds(store: CollectionsStore) -> None:
    data = _draft()
    del data["kpi_thresholds"]
    with pytest.raises(ValidationError):
        store.create(data)


def test_validation_rejects_bad_status(store: CollectionsStore) -> None:
    with pytest.raises(ValidationError):
        store.create(_draft(status="live"))


def test_validation_rejects_unknown_fields(store: CollectionsStore) -> None:
    with pytest.raises(ValidationError):
        store.create(_draft(slogan="nope"))


def test_validation_rejects_brand_lock_violation(store: CollectionsStore) -> None:
    data = _draft()
    data["illustration_rules"] = {**data["illustration_rules"], "no_mixed_styles": False}
    with pytest.raises(ValidationError):
        store.create(data)


def test_atomic_write_leaves_no_tmp_residue(store: CollectionsStore) -> None:
    store.create(_draft())
    leftovers = list(store._root.glob("*.tmp"))
    assert leftovers == []
    assert (store._root / "vibe-coding.yaml").is_file()


def test_mtime_conflict_rejects_stale_update(store: CollectionsStore) -> None:
    created = store.create(_draft())
    store.update("vibe-coding", {"theme": "changed underneath"})
    # Deterministically stale: any mtime older than the stored one conflicts,
    # regardless of filesystem timestamp granularity.
    with pytest.raises(MtimeConflict):
        store.update("vibe-coding", {"theme": "stale"}, expected_mtime=created["mtime"] - 1)
    assert store.get("vibe-coding")["contract"]["theme"] == "changed underneath"


def test_update_rejects_status_transition(store: CollectionsStore) -> None:
    store.create(_draft())
    with pytest.raises(ValueError, match="lifecycle"):
        store.update("vibe-coding", {"status": "active"})


def test_update_rejects_collection_id_change(store: CollectionsStore) -> None:
    store.create(_draft())
    with pytest.raises(ValueError, match="immutable"):
        store.update("vibe-coding", {"collection_id": "other"})


# --------------------------------------------------------------------- API


class FakeWriter:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def record(self, **kwargs: Any) -> None:
        self.rows.append(kwargs)


class Harness:
    def __init__(self, role: str = ROLE_ADMIN, root: Optional[Path] = None) -> None:
        import tempfile

        self.root = root or Path(tempfile.mkdtemp()) / "collections"
        self.store = CollectionsStore(self.root)
        self.writer = FakeWriter()
        app = FastAPI()
        app.include_router(collections_router.router)
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "op@x.y", role)
        app.dependency_overrides[get_collections_store] = lambda: self.store
        app.dependency_overrides[get_audit_writer] = lambda: self.writer
        self.client = TestClient(app, raise_server_exceptions=False)


def test_api_create_lists_and_details() -> None:
    h = Harness()
    created = h.client.post("/api/collections", json=_draft()).json()
    assert created["id"] == "vibe-coding"
    listed = h.client.get("/api/collections").json()
    assert [i["id"] for i in listed["items"]] == ["vibe-coding"]
    detail = h.client.get("/api/collections/vibe-coding").json()
    assert detail["contract"]["theme"] == "Vibe Coding"
    assert (h.root / "vibe-coding.yaml").is_file()  # file appears under collections/


def test_api_list_filter_and_404() -> None:
    h = Harness()
    h.client.post("/api/collections", json=_draft("a"))
    h.client.post("/api/collections", json=_draft("b"))
    assert len(h.client.get("/api/collections", params={"status": "draft"}).json()["items"]) == 2
    assert h.client.get("/api/collections", params={"status": "bogus"}).status_code == 422
    assert h.client.get("/api/collections/nope").status_code == 404


def test_api_create_rejects_invalid_with_field_errors() -> None:
    h = Harness()
    data = _draft()
    del data["kpi_thresholds"]
    response = h.client.post("/api/collections", json=data)
    assert response.status_code == 422
    assert any("kpi_thresholds" in str(err.get("loc")) for err in response.json()["detail"])


def test_api_create_collision_is_409() -> None:
    h = Harness()
    assert h.client.post("/api/collections", json=_draft()).status_code == 201
    assert h.client.post("/api/collections", json=_draft()).status_code == 409


def test_api_update_writes_file_and_audit_row() -> None:
    h = Harness()
    h.client.post("/api/collections", json=_draft())
    updated = h.client.patch("/api/collections/vibe-coding", json={"theme": "v2"}).json()
    assert updated["contract"]["theme"] == "v2"
    on_disk = yaml.safe_load((h.root / "vibe-coding.yaml").read_text(encoding="utf-8"))
    assert on_disk["theme"] == "v2"
    create_row, update_row = h.writer.rows
    assert create_row["action"] == "collection.create"
    assert update_row["action"] == "collection.update"
    assert update_row["before"]["theme"] == "Vibe Coding"
    assert update_row["after"]["theme"] == "v2"


def test_api_update_rejects_status_transition() -> None:
    h = Harness()
    h.client.post("/api/collections", json=_draft())
    assert h.client.patch("/api/collections/vibe-coding", json={"status": "active"}).status_code == 422


def test_api_role_matrix() -> None:
    viewer, operator = Harness(role=ROLE_VIEWER), Harness(role=ROLE_OPERATOR)
    viewer.client.post("/api/collections", json=_draft())
    assert viewer.client.get("/api/collections").status_code == 200  # Viewer+ reads
    assert viewer.client.post("/api/collections", json=_draft("x")).status_code == 403
    assert operator.client.post("/api/collections", json=_draft()).status_code == 403  # Admin only


def test_api_requires_auth() -> None:
    app = FastAPI()
    app.include_router(collections_router.router)
    client = TestClient(app)
    assert client.get("/api/collections").status_code == 401
    assert client.post("/api/collections", json={}).status_code == 401


def test_dashboard_shape_unchanged_on_store() -> None:
    from api.app.dashboard import summarize_collections

    h = Harness()
    h.client.post("/api/collections", json=_draft())
    contracts = [record["contract"] for record in h.store.list()]
    summary = summarize_collections(contracts)
    assert summary["count"] == 1
    assert summary["items"][0]["slug"] == "vibe-coding"
