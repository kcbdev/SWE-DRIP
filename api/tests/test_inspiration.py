"""Inspiration ingest contracts (PBI-049, spec C3) — offline, tmp dir + fakes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.audit import get_audit_writer
from api.app.collections_store import CollectionsStore
from api.app.inspiration import (
    InspirationStore,
    MAX_BYTES,
    resolve_collections_root,
    sniff_image,
)
from api.app.routers import inspiration as inspiration_router

PNG = (
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    + b"\x00\x00\x00\x0dIHDR" + b"\x00" * 13
)
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


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
    def record(self, **kwargs: Any) -> None:
        pass


def _client(role: str, store: InspirationStore) -> TestClient:
    app = FastAPI()
    app.include_router(inspiration_router.router)
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", role)
    app.dependency_overrides[get_audit_writer] = lambda: _NoopAudit()
    app.dependency_overrides[inspiration_router.get_inspiration_store] = lambda: store
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def harness(tmp_path: Path) -> tuple[TestClient, InspirationStore]:
    root = tmp_path / "collections"
    store = InspirationStore(root, _collections(tmp_path))
    return _client(ROLE_ADMIN, store), store


class TestSniff:
    def test_png_and_jpeg_accepted(self) -> None:
        assert sniff_image(PNG, "image/png") == ".png"
        assert sniff_image(JPEG, "image/jpeg") == ".jpg"

    def test_wrong_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="content type"):
            sniff_image(PNG, "image/jpeg")

    def test_non_image_rejected(self) -> None:
        with pytest.raises(ValueError, match="not a PNG or JPEG"):
            sniff_image(b"GIF89a" + b"\x00" * 16, "image/png")

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="unsupported"):
            sniff_image(PNG, "image/gif")

    def test_oversize_rejected(self) -> None:
        with pytest.raises(ValueError, match="exceeds"):
            sniff_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_BYTES + 1), "image/png")


class TestUploadRoundTrip:
    def test_upload_list_serve_delete(self, harness) -> None:
        client, store = harness
        resp = client.post(
            "/api/collections/vibe/inspiration",
            files={"file": ("ref.png", PNG, "image/png")},
            data={"note": "line quality", "source_url": "https://example.com/r"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["filename"].endswith(".png") and body["size_bytes"] == len(PNG)
        assert body["note"] == "line quality"

        listed = client.get("/api/collections/vibe/inspiration").json()
        assert len(listed["assets"]) == 1
        assert listed["assets"][0]["id"] == body["id"]
        sidecar = store._root / "vibe.assets" / f"{body['id']}.json"
        proven = json.loads(sidecar.read_text(encoding="utf-8"))
        assert proven["source_url"] == "https://example.com/r"
        assert proven["actor_user_id"] == "u-9" and proven["created_at"]

        served = client.get(f"/api/collections/vibe/inspiration/{body['id']}/file")
        assert served.status_code == 200
        assert served.content == PNG
        assert served.headers["content-type"] == "image/png"

        assert client.delete(
            f"/api/collections/vibe/inspiration/{body['id']}").status_code == 200
        assert client.get("/api/collections/vibe/inspiration").json()["assets"] == []

    def test_link_ref_round_trip(self, harness) -> None:
        client, store = harness
        resp = client.post("/api/collections/vibe/inspiration",
                           json={"url": "https://example.com/board", "note": "palette"})
        assert resp.status_code == 201
        assert resp.json() == {"url": "https://example.com/board", "note": "palette"}
        listed = client.get("/api/collections/vibe/inspiration").json()
        assert listed["refs"] == [{"url": "https://example.com/board", "note": "palette"}]

    def test_unknown_collection_404(self, harness) -> None:
        client, _ = harness
        assert client.get("/api/collections/ghost/inspiration").status_code == 404
        assert client.post("/api/collections/ghost/inspiration",
                           json={"url": "https://example.com/x"}).status_code == 404


class TestRejections:
    def test_path_guards_reject_traversal_directly(self, tmp_path: Path) -> None:
        from api.app.inspiration import _check_asset_id, _slug_dir

        store = InspirationStore(tmp_path / "collections", _collections(tmp_path))
        for bad_slug in ("../etc", "..\\etc", ".hidden", "a/b", ""):
            with pytest.raises(ValueError):
                store.list(bad_slug)
            with pytest.raises(ValueError):
                _slug_dir(tmp_path, bad_slug)
        for bad_id in ("../../x", "..", "a/b", "x.png", ""):
            with pytest.raises(ValueError):
                _check_asset_id(bad_id)
            with pytest.raises(ValueError):
                store.read_bytes("vibe", bad_id)

    def test_traversal_filename_stored_uuid_only(self, harness) -> None:
        client, store = harness
        resp = client.post(
            "/api/collections/vibe/inspiration",
            files={"file": ("../../evil.png", PNG, "image/png")},
            data={"note": "traversal attempt"},
        )
        assert resp.status_code == 201
        assert resp.json()["filename"] != "../../evil.png"
        assert "/" not in resp.json()["filename"]

    def test_gif_bytes_rejected(self, harness) -> None:
        client, _ = harness
        resp = client.post(
            "/api/collections/vibe/inspiration",
            files={"file": ("ref.png", b"GIF89a" + b"\x00" * 16, "image/png")},
        )
        assert resp.status_code == 400

    def test_missing_file_part_400(self, harness) -> None:
        client, _ = harness
        resp = client.post(
            "/api/collections/vibe/inspiration",
            files={"other": ("x.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400

    def test_link_without_url_422(self, harness) -> None:
        client, _ = harness
        assert client.post("/api/collections/vibe/inspiration",
                           json={"url": "  "}).status_code in (400, 422)
        assert client.post("/api/collections/vibe/inspiration",
                           json={"url": "ftp://example.com/x"}).status_code in (400, 422)

    def test_traversal_asset_id_404(self, harness) -> None:
        client, _ = harness
        assert client.get("/api/collections/vibe/inspiration/../x/file").status_code in (404, 422)
        assert client.delete("/api/collections/vibe/inspiration/..").status_code == 404

    def test_oversize_rejected(self, harness) -> None:
        client, _ = harness
        big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_BYTES + 1)
        resp = client.post("/api/collections/vibe/inspiration",
                           files={"file": ("big.png", big, "image/png")})
        assert resp.status_code == 400

    def test_audit_rows_written(self, harness) -> None:
        from api.app.audit import get_audit_writer

        client, store = harness
        calls: list[dict[str, Any]] = []

        class FakeAudit:
            def record(self, **kwargs: Any) -> None:
                calls.append(kwargs)

        app = FastAPI()
        app.include_router(inspiration_router.router)
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "a@b.c", ROLE_ADMIN)
        app.dependency_overrides[get_audit_writer] = lambda: FakeAudit()
        app.dependency_overrides[inspiration_router.get_inspiration_store] = lambda: store
        audited = TestClient(app, raise_server_exceptions=False)
        upload = audited.post("/api/collections/vibe/inspiration",
                              files={"file": ("r.png", PNG, "image/png")}).json()
        audited.post("/api/collections/vibe/inspiration",
                     json={"url": "https://example.com/b"})
        audited.delete(f"/api/collections/vibe/inspiration/{upload['id']}")
        actions = [c["action"] for c in calls]
        assert actions == ["inspiration.asset.add", "inspiration.link.add",
                           "inspiration.asset.delete"]
        assert all(c["entity_id"] == "vibe" for c in calls)
        # Both files gone from disk (bytes + sidecar, not just unlisted).
        leftovers = list((store._root / "vibe.assets").iterdir())
        assert leftovers == []


class TestRoles:
    def test_viewer_reads_but_cannot_write(self, tmp_path: Path) -> None:
        store = InspirationStore(tmp_path / "collections", _collections(tmp_path))
        viewer = _client(ROLE_VIEWER, store)
        assert viewer.get("/api/collections/vibe/inspiration").status_code == 200
        assert viewer.post("/api/collections/vibe/inspiration",
                           json={"url": "https://example.com/x"}).status_code == 403
        assert viewer.delete("/api/collections/vibe/inspiration/abc").status_code == 403


class TestEnvRoot:
    def test_env_override(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("SWE_DRIP_COLLECTIONS_DIR", str(tmp_path / "elsewhere"))
        assert resolve_collections_root() == tmp_path / "elsewhere"

    def test_default_is_repo_collections(self, monkeypatch) -> None:
        monkeypatch.delenv("SWE_DRIP_COLLECTIONS_DIR", raising=False)
        assert resolve_collections_root().name == "collections"
