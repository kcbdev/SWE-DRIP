"""Audit writer/read contract tests (offline)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.audit import (
    SYSTEM_ACTOR,
    AuditFilters,
    build_audit_query,
    build_audit_row,
    get_audit_reader,
)
from api.app.auth import ROLE_ADMIN, ROLE_VIEWER, Actor, get_current_actor
from api.app.routers import audit as audit_router


# ------------------------------------------------------------------- writer


def test_build_row_requires_actor() -> None:
    with pytest.raises(ValueError):
        build_audit_row(actor_user_id="", action="role.change", entity_type="user")


def test_build_row_requires_action_and_entity() -> None:
    with pytest.raises(ValueError):
        build_audit_row(actor_user_id="u-1", action="", entity_type="user")
    with pytest.raises(ValueError):
        build_audit_row(actor_user_id="u-1", action="role.change", entity_type="")


def test_build_row_shapes_payload() -> None:
    row = build_audit_row(
        actor_user_id="u-1",
        action="role.change",
        entity_type="user",
        entity_id="u-2",
        before={"role": "viewer"},
        after={"role": "operator"},
    )
    assert row == {
        "actor_user_id": "u-1",
        "action": "role.change",
        "entity_type": "user",
        "entity_id": "u-2",
        "before_json": {"role": "viewer"},
        "after_json": {"role": "operator"},
    }


def test_system_actor_is_explicit_constant() -> None:
    assert SYSTEM_ACTOR == "system"


# ------------------------------------------------------------ filter builder


def _sql(filters: AuditFilters) -> str:
    return str(build_audit_query(filters).compile(compile_kwargs={"literal_binds": True}))


def test_query_without_filters_has_no_where() -> None:
    assert "WHERE" not in _sql(AuditFilters())


def test_query_applies_each_filter() -> None:
    sql = _sql(
        AuditFilters(
            actor="u-1",
            action="role.change",
            entity_type="user",
            entity_id="u-2",
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end=datetime(2026, 12, 31, tzinfo=timezone.utc),
            limit=10,
        )
    )
    assert "actor_user_id = 'u-1'" in sql
    assert "action = 'role.change'" in sql
    assert "entity_type = 'user'" in sql
    assert "entity_id = 'u-2'" in sql
    assert "created_at >= " in sql
    assert "created_at <= " in sql
    assert "LIMIT 10" in sql


# ------------------------------------------------------------------ read API


class FakeReader:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def list_entries(self, filters: AuditFilters) -> list[dict]:
        return list(self.rows)


ROWS = [
    {
        "id": 1,
        "actor_user_id": "u-1",
        "created_at": "2026-09-13T10:00:00+00:00",
        "action": "role.change",
        "entity_type": "user",
        "entity_id": "u-2",
        "before_json": {"role": "viewer"},
        "after_json": {"role": "operator"},
    }
]


def _client(role: str) -> TestClient:
    app = FastAPI()
    app.include_router(audit_router.router)
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-1", "a@b.c", role)
    app.dependency_overrides[get_audit_reader] = lambda: FakeReader(ROWS)
    return TestClient(app)


@pytest.mark.parametrize("role", [ROLE_ADMIN, ROLE_VIEWER])
def test_viewer_plus_can_read_json(role: str) -> None:
    response = _client(role).get("/api/audit")
    assert response.status_code == 200
    assert response.json()[0]["action"] == "role.change"


def test_csv_export_shape() -> None:
    response = _client(ROLE_VIEWER).get("/api/audit?format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("id,actor_user_id,created_at,action")
    assert "role.change" in lines[1]


def test_unauthenticated_read_is_401() -> None:
    app = FastAPI()
    app.include_router(audit_router.router)
    assert TestClient(app).get("/api/audit").status_code == 401


def test_invalid_format_is_422() -> None:
    assert _client(ROLE_VIEWER).get("/api/audit?format=xml").status_code == 422
