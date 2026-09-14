"""Collections lifecycle: candidates, approve (A8), retire + survivor (A9)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor, get_current_actor
from api.app.audit import get_audit_writer
from api.app.collections_store import CollectionsStore, get_collections_store
from api.app.hitl import InterruptInfo, get_approval_index, get_gate_source, get_hitl_service
from api.app.routers import collections as collections_router
from api.tests.test_collections_store import FakeWriter, _draft


def _cluster(theme: str = "Vibe Coding") -> dict[str, Any]:
    return {
        "cluster": {"cluster_id": "cluster-1", "theme": theme, "brief_ids": ["b-1", "b-2"]},
        "member_styles": ["terminal-brutalist", "terminal-brutalist"],
    }


def _complete(slug: str = "vibe-coding") -> dict[str, Any]:
    """Approval-complete draft (filled palette + thresholds)."""
    return _draft(slug)


class FakeGates:
    def __init__(self, infos: Optional[list[InterruptInfo]] = None) -> None:
        self.infos = infos or []

    def list_interrupts(self) -> list[InterruptInfo]:
        return list(self.infos)


class FakeIndex:
    def __init__(self) -> None:
        self.rows: dict[int, dict[str, Any]] = {}
        self._next = 1

    def list_open(self) -> list[dict[str, Any]]:
        return [r for r in self.rows.values() if r["status"] == "pending"]

    def add_pending(self, run_id: str, node: str) -> dict[str, Any]:
        row = {"id": self._next, "run_id": run_id, "node": node, "status": "pending"}
        self.rows[self._next] = row
        self._next += 1
        return row


class FakeService:
    def __init__(self) -> None:
        self.decisions: list[tuple[int, str]] = []

    def decide(self, item_id: int, **kwargs: Any) -> dict[str, Any]:
        self.decisions.append((item_id, kwargs.get("action")))
        return {"resumed": True}


class Harness:
    def __init__(
        self,
        role: str = ROLE_ADMIN,
        root: Optional[Path] = None,
        gates: Optional[FakeGates] = None,
    ) -> None:
        import tempfile

        self.root = root or Path(tempfile.mkdtemp()) / "collections"
        self.store = CollectionsStore(self.root)
        self.writer = FakeWriter()
        self.gates = gates or FakeGates()
        self.index = FakeIndex()
        self.service = FakeService()
        app = FastAPI()
        app.include_router(collections_router.router)
        app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "op@x.y", role)
        app.dependency_overrides[get_collections_store] = lambda: self.store
        app.dependency_overrides[get_audit_writer] = lambda: self.writer
        app.dependency_overrides[get_hitl_service] = lambda: self.service
        app.dependency_overrides[get_gate_source] = lambda: self.gates
        app.dependency_overrides[get_approval_index] = lambda: self.index
        self.client = TestClient(app, raise_server_exceptions=False)


def _contract_info(run_id: str, slug: str) -> InterruptInfo:
    return InterruptInfo(
        run_id=run_id,
        node="contract_approval",
        payload={"contracts": [{"collection_id": slug, "theme": "Vibe Coding"}]},
        interrupt_id="i-1",
    )


# --------------------------------------------------------------- candidates


def test_candidate_from_cluster_fixture() -> None:
    h = Harness()
    body = h.client.post("/api/collections/candidates", json=_cluster()).json()
    assert body["id"] == "vibe-coding"  # slugified theme
    assert body["cluster_id"] == "cluster-1"
    assert body["contract"]["status"] == "draft"
    assert body["contract"]["style_archetype"] == "terminal-brutalist"  # from member styles
    on_disk = yaml.safe_load((h.root / "vibe-coding.yaml").read_text(encoding="utf-8"))
    assert on_disk["collection_id"] == "vibe-coding"
    (row,) = h.writer.rows
    assert row["action"] == "collection.candidate"
    assert row["before"] == {"cluster_id": "cluster-1"}


def test_candidate_rejects_cluster_without_styles() -> None:
    h = Harness()
    bad = {"cluster": {"cluster_id": "c", "theme": "T", "brief_ids": []}, "member_styles": []}
    assert h.client.post("/api/collections/candidates", json=bad).status_code == 422


def test_candidate_slug_collision_is_409() -> None:
    h = Harness()
    assert h.client.post("/api/collections/candidates", json=_cluster()).status_code == 201
    assert h.client.post("/api/collections/candidates", json=_cluster()).status_code == 409


# ------------------------------------------------------------------ approve


def test_approve_sets_active_stamp_audit_and_resume() -> None:
    h = Harness(gates=FakeGates([_contract_info("run-7", "vibe-coding")]))
    h.index.add_pending("run-7", "contract_approval")
    h.client.post("/api/collections", json=_complete())
    body = h.client.post("/api/collections/vibe-coding/approve").json()
    assert body["contract"]["status"] == "active"
    assert body["contract"]["approved_at"]
    assert h.service.decisions == [(1, "approve")]  # resume dispatched exactly once
    assert body["resume"]["resumed"] is True
    assert body["resume"]["paused_run"] == {"run_id": "run-7", "node": "contract_approval"}
    actions = [row["action"] for row in h.writer.rows]
    assert actions == ["collection.create", "collection.approve"]
    approved = yaml.safe_load((h.root / "vibe-coding.yaml").read_text(encoding="utf-8"))
    assert approved["status"] == "active"  # YAML valid + active on disk


def test_approve_without_paused_run_still_activates() -> None:
    h = Harness()  # no live gates
    h.client.post("/api/collections", json=_complete())
    body = h.client.post("/api/collections/vibe-coding/approve").json()
    assert body["contract"]["status"] == "active"
    assert h.service.decisions == []
    assert body["resume"] == {"attempted": False, "resumed": False, "paused_run": None}


def test_approve_rejects_incomplete_draft() -> None:
    h = Harness()
    h.client.post("/api/collections/candidates", json=_cluster())  # placeholders, no palette
    response = h.client.post("/api/collections/vibe-coding/approve")
    assert response.status_code == 422
    assert any("palette" in str(err) for err in response.json()["detail"])
    assert h.client.get("/api/collections/vibe-coding").json()["contract"]["status"] == "draft"


def test_approve_only_from_draft() -> None:
    h = Harness()
    h.client.post("/api/collections", json=_complete())
    assert h.client.post("/api/collections/vibe-coding/approve").status_code == 200
    assert h.client.post("/api/collections/vibe-coding/approve").status_code == 409


def test_approve_unknown_is_404() -> None:
    assert Harness().client.post("/api/collections/nope/approve").status_code == 404


# ------------------------------------------------------------------- retire


def test_retire_with_survivor_keeps_product_live_and_flagged() -> None:
    h = Harness()
    h.client.post("/api/collections", json=_complete())
    h.client.post("/api/collections/vibe-coding/approve")
    body = h.client.post(
        "/api/collections/vibe-coding/retire", json={"survivor_product_ids": ["fw-1"]}
    ).json()
    assert body["contract"]["status"] == "retired"
    assert body["contract"]["retired_at"]
    assert body["contract"]["survivor_products"] == ["fw-1"]
    assert body["survivors_live"] == ["fw-1"]  # flagged live in the response + audit
    on_disk = yaml.safe_load((h.root / "vibe-coding.yaml").read_text(encoding="utf-8"))
    assert on_disk["survivor_products"] == ["fw-1"]
    retire_row = h.writer.rows[-1]
    assert retire_row["action"] == "collection.retire"
    assert retire_row["after"]["survivor_products"] == ["fw-1"]


def test_retire_without_survivor_deactivates_membership() -> None:
    h = Harness()
    h.client.post("/api/collections", json=_complete())
    h.client.post("/api/collections/vibe-coding/approve")
    body = h.client.post("/api/collections/vibe-coding/retire", json={}).json()
    assert body["contract"]["status"] == "retired"
    assert body["contract"]["survivor_products"] == []
    assert body["survivors_live"] == []


def test_retire_only_from_active() -> None:
    h = Harness()
    h.client.post("/api/collections", json=_complete())
    assert h.client.post("/api/collections/vibe-coding/retire", json={}).status_code == 409


def test_retire_rejects_non_string_survivors() -> None:
    h = Harness()
    h.client.post("/api/collections", json=_complete())
    h.client.post("/api/collections/vibe-coding/approve")
    assert h.client.post("/api/collections/vibe-coding/retire", json={"survivor_product_ids": [7]}).status_code == 422


# -------------------------------------------------------------------- roles


def test_lifecycle_role_matrix() -> None:
    admin = Harness(role=ROLE_ADMIN)
    admin.client.post("/api/collections", json=_complete())
    operator = Harness(role=ROLE_OPERATOR)
    operator.store = admin.store  # share the filesystem
    operator.client.post("/api/collections/candidates", json=_cluster("Other"))
    # Operator may approve (A8) but not retire or create candidates.
    assert operator.client.post("/api/collections/candidates", json=_cluster()).status_code == 403
    assert operator.client.post("/api/collections/vibe-coding/approve").status_code == 200
    assert operator.client.post("/api/collections/vibe-coding/retire", json={}).status_code == 403
    viewer = Harness(role=ROLE_VIEWER)
    viewer.store = admin.store
    assert viewer.client.post("/api/collections/vibe-coding/approve").status_code == 403
