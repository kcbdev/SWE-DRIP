"""Admin-only user management (spec C3).

Every route is gated by ``require_role(admin)`` — Operator and Viewer receive
403 regardless of any UI state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth import ROLE_ADMIN, ROLES, Actor
from ..rbac import require_role
from ..users import UserStore, UserRecord, get_user_store

router = APIRouter(prefix="/api/users", tags=["users"])

AdminOnly = Depends(require_role(ROLE_ADMIN))


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
) -> dict[str, object]:
    _validate_role(payload.role)
    updated = store.set_role(user_id, payload.role)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return _record(updated)


@router.post("/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    actor: Actor = AdminOnly,
    store: UserStore = Depends(get_user_store),
) -> dict[str, object]:
    updated = store.deactivate(user_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return _record(updated)
