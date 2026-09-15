"""Admin-only user management (spec C3).

Every route is gated by ``require_role(admin)`` — Operator and Viewer receive
403 regardless of any UI state.

Two safety properties beyond the role gate:
- Role changes and deactivations are **audited** (before/after, append-only).
- The invariant **at least one active admin must always remain** is enforced
  server-side. Demoting or deactivating an admin is refused when it would leave
  none, which is what protects the organisation from losing every admin-only
  surface. Self-demotion is allowed while another active admin exists.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, ROLES, Actor
from ..rbac import require_role
from ..users import UserStore, UserRecord, get_user_store

router = APIRouter(prefix="/api/users", tags=["users"])

AdminOnly = Depends(require_role(ROLE_ADMIN))

LAST_ADMIN_REFUSAL = (
    "Refusing: this would leave no active admin. Promote another user to admin first."
)


class InviteRequest(BaseModel):
    email: str
    name: str = ""
    role: str = "viewer"


class RoleRequest(BaseModel):
    role: str


def _validate_role(role: str) -> None:
    if role not in ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"role must be one of {', '.join(ROLES)}",
        )


def _find(store: UserStore, user_id: str) -> UserRecord | None:
    return next((user for user in store.list_users() if user.id == user_id), None)


def _guard_last_admin(store: UserStore, target: UserRecord | None, still_admin: bool) -> None:
    """Refuse the change when it would remove the last active admin."""
    if target is None or not (target.role == ROLE_ADMIN and target.active):
        return  # target is not an active admin — nothing to protect
    if still_admin:
        return  # target stays an active admin
    others = [
        user
        for user in store.list_users()
        if user.id != target.id and user.role == ROLE_ADMIN and user.active
    ]
    if not others:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=LAST_ADMIN_REFUSAL)


def _record(record: UserRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "email": record.email,
        "name": record.name,
        "role": record.role,
        "active": record.active,
    }


@router.get("")
def list_users(
    actor: Actor = AdminOnly,
    store: UserStore = Depends(get_user_store),
) -> list[dict[str, object]]:
    return [_record(user) for user in store.list_users()]


@router.post("", status_code=status.HTTP_201_CREATED)
def invite_user(
    payload: InviteRequest,
    actor: Actor = AdminOnly,
    store: UserStore = Depends(get_user_store),
) -> dict[str, object]:
    _validate_role(payload.role)
    if not payload.email or "@" not in payload.email:
        raise HTTPException(status_code=422, detail="valid email required")
    return _record(store.invite_user(payload.email, payload.name, payload.role))


@router.patch("/{user_id}/role")
def change_role(
    user_id: str,
    payload: RoleRequest,
    actor: Actor = AdminOnly,
    store: UserStore = Depends(get_user_store),
    audit: AuditWriter = Depends(get_audit_writer),
) -> dict[str, object]:
    _validate_role(payload.role)
    before = _find(store, user_id)
    if before is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    _guard_last_admin(store, before, still_admin=(payload.role == ROLE_ADMIN))
    updated = store.set_role(user_id, payload.role)
    if updated is None:  # pragma: no cover - raced deletion
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    audit.record(
        action="users.role.update",
        entity_type="user",
        entity_id=user_id,
        before={"role": before.role},
        after={"role": updated.role},
        actor_user_id=actor.user_id,
    )
    return _record(updated)


@router.post("/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    actor: Actor = AdminOnly,
    store: UserStore = Depends(get_user_store),
    audit: AuditWriter = Depends(get_audit_writer),
) -> dict[str, object]:
    before = _find(store, user_id)
    if before is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    _guard_last_admin(store, before, still_admin=False)
    updated = store.deactivate(user_id)
    if updated is None:  # pragma: no cover - raced deletion
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    audit.record(
        action="users.deactivate",
        entity_type="user",
        entity_id=user_id,
        before={"active": before.active},
        after={"active": updated.active},
        actor_user_id=actor.user_id,
    )
    return _record(updated)
