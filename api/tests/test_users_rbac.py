"""User-management RBAC matrix (offline; in-memory fake store)."""

from __future__ import annotations

from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor, get_current_actor
from api.app.routers import users as users_router
from api.app.users import UserRecord, get_user_store


class FakeUserStore:
    def __init__(self) -> None:
        self.users: dict[str, UserRecord] = {
            "u-1": UserRecord("u-1", "admin@example.com", "Admin", ROLE_ADMIN, True)
        }

    def list_users(self) -> list[UserRecord]:
        return list(self.users.values())

    def invite_user(self, email: str, name: str, role: str) -> UserRecord:
        new_id = f"u-{len(self.users) + 1}"
        record = UserRecord(new_id, email, name, role, True)
        self.users[new_id] = record
        return record

    def set_role(self, user_id: str, role: str) -> Optional[UserRecord]:
        current = self.users.get(user_id)
        if current is None:
            return None
        updated = UserRecord(current.id, current.email, current.name, role, current.active)
        self.users[user_id] = updated
        return updated

    def deactivate(self, user_id: str) -> Optional[UserRecord]:
        current = self.users.get(user_id)
        if current is None:
            return None
        updated = UserRecord(current.id, current.email, current.name, current.role, False)
        self.users[user_id] = updated
        return updated


def build_client(role: str) -> tuple[TestClient, FakeUserStore]:
    app = FastAPI()
    app.include_router(users_router.router)
    store = FakeUserStore()
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-1", "admin@example.com", role)
    app.dependency_overrides[get_user_store] = lambda: store
    return TestClient(app), store


ENDPOINTS = [
    ("GET", "/api/users", None),
    ("POST", "/api/users", {"email": "new@example.com", "name": "New", "role": "viewer"}),
    ("PATCH", "/api/users/u-1/role", {"role": "operator"}),
    ("POST", "/api/users/u-1/deactivate", None),
]


@pytest.mark.parametrize(("method", "path", "body"), ENDPOINTS)
@pytest.mark.parametrize("role", [ROLE_OPERATOR, ROLE_VIEWER])
def test_non_admin_is_403(method: str, path: str, body, role: str) -> None:
    client, _ = build_client(role)
    response = client.request(method, path, json=body)
    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path", "body"), ENDPOINTS)
def test_admin_is_allowed(method: str, path: str, body) -> None:
    client, _ = build_client(ROLE_ADMIN)
    response = client.request(method, path, json=body)
    assert response.status_code in (200, 201)


def test_admin_invite_creates_user_and_rejects_bad_role() -> None:
    client, store = build_client(ROLE_ADMIN)
    created = client.post(
        "/api/users", json={"email": "ops@example.com", "name": "Ops", "role": "operator"}
    )
    assert created.status_code == 201
    assert created.json()["role"] == "operator"
    assert len(store.users) == 2

    bad = client.post("/api/users", json={"email": "x@example.com", "role": "superuser"})
    assert bad.status_code == 422


def test_admin_role_change_and_deactivate() -> None:
    client, _ = build_client(ROLE_ADMIN)
    changed = client.patch("/api/users/u-1/role", json={"role": "viewer"})
    assert changed.status_code == 200 and changed.json()["role"] == "viewer"
    off = client.post("/api/users/u-1/deactivate")
    assert off.status_code == 200 and off.json()["active"] is False


def test_unknown_user_is_404() -> None:
    client, _ = build_client(ROLE_ADMIN)
    assert client.patch("/api/users/nope/role", json={"role": "viewer"}).status_code == 404
    assert client.post("/api/users/nope/deactivate").status_code == 404
