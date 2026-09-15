"""User-management RBAC matrix + safety invariants (offline; in-memory fake)."""

from __future__ import annotations

from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.audit import get_audit_writer
from api.app.auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor, get_current_actor
from api.app.routers import users as users_router
from api.app.users import UserRecord, get_user_store

ACTOR_ID = "u-1"


class FakeUserStore:
    def __init__(self, admins: int = 1) -> None:
        # u-1 is always the acting admin; extra admins support the multi-admin cases.
        self.users: dict[str, UserRecord] = {
            ACTOR_ID: UserRecord(ACTOR_ID, "admin@example.com", "Admin", ROLE_ADMIN, True),
            "u-2": UserRecord("u-2", "ops@example.com", "Ops", ROLE_OPERATOR, True),
        }
        for index in range(2, admins + 1):
            user_id = f"u-a{index}"
            self.users[user_id] = UserRecord(
                user_id, f"admin{index}@example.com", f"Admin {index}", ROLE_ADMIN, True
            )
        self._next = len(self.users) + 1

    def list_users(self) -> list[UserRecord]:
        return list(self.users.values())

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


class RecordingAudit:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def build_client(
    role: str, *, admins: int = 1
) -> tuple[TestClient, FakeUserStore, RecordingAudit]:
    app = FastAPI()
    app.include_router(users_router.router)
    store = FakeUserStore(admins=admins)
    audit = RecordingAudit()
    app.dependency_overrides[get_current_actor] = lambda: Actor(
        ACTOR_ID, "admin@example.com", role
    )
    app.dependency_overrides[get_user_store] = lambda: store
    app.dependency_overrides[get_audit_writer] = lambda: audit
    return TestClient(app), store, audit


# Targets a NON-admin (u-2) so the RBAC matrix is independent of the
# last-admin guard, which is tested separately below.
ENDPOINTS = [
    ("GET", "/api/users", None),
    ("PATCH", "/api/users/u-2/role", {"role": "viewer"}),
    ("POST", "/api/users/u-2/deactivate", None),
]


@pytest.mark.parametrize(("method", "path", "body"), ENDPOINTS)
@pytest.mark.parametrize("role", [ROLE_OPERATOR, ROLE_VIEWER])
def test_non_admin_is_403(method: str, path: str, body, role: str) -> None:
    client, _, _ = build_client(role)
    response = client.request(method, path, json=body)
    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path", "body"), ENDPOINTS)
def test_admin_is_allowed(method: str, path: str, body) -> None:
    client, _, _ = build_client(ROLE_ADMIN)
    response = client.request(method, path, json=body)
    assert response.status_code in (200, 201)


def test_user_creation_is_not_exposed_by_this_api() -> None:
    """Better Auth owns credential storage (spec C1) — the Python invite route
    created credential-less users who could never sign in, so it was removed."""
    client, store, _ = build_client(ROLE_ADMIN)
    response = client.post(
        "/api/users",
        json={"email": "design@example.com", "name": "Design", "role": "operator"},
    )
    assert response.status_code == 405  # Method Not Allowed
    assert len(store.users) == 2  # nothing created


def test_role_change_and_deactivate() -> None:
    client, _, _ = build_client(ROLE_ADMIN)
    changed = client.patch("/api/users/u-2/role", json={"role": "viewer"})
    assert changed.status_code == 200 and changed.json()["role"] == "viewer"
    off = client.post("/api/users/u-2/deactivate")
    assert off.status_code == 200 and off.json()["active"] is False


def test_unknown_user_is_404() -> None:
    client, _, _ = build_client(ROLE_ADMIN)
    assert client.patch("/api/users/nope/role", json={"role": "viewer"}).status_code == 404
    assert client.post("/api/users/nope/deactivate").status_code == 404


# ---------------------------------------------------------------------------
# Last-admin invariant (never leave the organisation without an admin)
# ---------------------------------------------------------------------------


def test_cannot_demote_the_only_admin() -> None:
    """The exact scenario that locked admin surfaces out in production."""
    client, store, audit = build_client(ROLE_ADMIN, admins=1)
    response = client.patch(f"/api/users/{ACTOR_ID}/role", json={"role": "operator"})
    assert response.status_code == 409
    assert "no active admin" in response.json()["detail"]
    # Nothing changed and nothing was audited.
    assert store.users[ACTOR_ID].role == ROLE_ADMIN
    assert audit.calls == []


def test_cannot_deactivate_the_only_admin() -> None:
    client, store, audit = build_client(ROLE_ADMIN, admins=1)
    response = client.post(f"/api/users/{ACTOR_ID}/deactivate")
    assert response.status_code == 409
    assert store.users[ACTOR_ID].active is True
    assert audit.calls == []


def test_self_demotion_allowed_when_another_admin_exists() -> None:
    """A second admin unblocks self-demotion — the guard is about coverage."""
    client, store, audit = build_client(ROLE_ADMIN, admins=2)
    response = client.patch(f"/api/users/{ACTOR_ID}/role", json={"role": "operator"})
    assert response.status_code == 200
    assert store.users[ACTOR_ID].role == ROLE_OPERATOR
    assert audit.calls[0]["action"] == "users.role.update"


def test_inactive_admin_does_not_count_as_coverage() -> None:
    client, store, _ = build_client(ROLE_ADMIN, admins=1)
    # A second admin who is deactivated must not satisfy the invariant.
    store.users[ACTOR_ID] = UserRecord(
        ACTOR_ID, "admin@example.com", "Admin", ROLE_ADMIN, True
    )
    store.users["u-a2"] = UserRecord(
        "u-a2", "admin2@example.com", "Admin 2", ROLE_ADMIN, False
    )
    response = client.patch(f"/api/users/{ACTOR_ID}/role", json={"role": "viewer"})
    assert response.status_code == 409


def test_promoting_a_user_to_admin_is_always_allowed() -> None:
    client, store, _ = build_client(ROLE_ADMIN, admins=1)
    response = client.patch("/api/users/u-2/role", json={"role": "admin"})
    assert response.status_code == 200
    assert store.users["u-2"].role == ROLE_ADMIN


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


def test_role_change_is_audited() -> None:
    client, _, audit = build_client(ROLE_ADMIN)
    client.patch("/api/users/u-2/role", json={"role": "admin"})
    assert len(audit.calls) == 1
    call = audit.calls[0]
    assert call["action"] == "users.role.update"
    assert call["entity_type"] == "user"
    assert call["entity_id"] == "u-2"
    assert call["before"] == {"role": ROLE_OPERATOR}
    assert call["after"] == {"role": ROLE_ADMIN}
    assert call["actor_user_id"] == ACTOR_ID


def test_deactivation_is_audited() -> None:
    client, _, audit = build_client(ROLE_ADMIN)
    client.post("/api/users/u-2/deactivate")
    assert len(audit.calls) == 1
    call = audit.calls[0]
    assert call["action"] == "users.deactivate"
    assert call["entity_id"] == "u-2"
    assert call["before"] == {"active": True}
    assert call["after"] == {"active": False}
