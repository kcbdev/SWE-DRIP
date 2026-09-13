"""User-management data access (Admin-only operations, spec C3).

The store is a small protocol so the API can be tested offline with an
in-memory fake; the SQL implementation targets Better Auth's own ``user`` table
(Better Auth remains the single owner of credentials — this store manages
profile/role/activation only; credential creation is delegated to Better Auth's
admin create-user flow at integration time).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional, Protocol

from sqlalchemy import text

from .auth import ROLE_VIEWER
from .db import get_engine


@dataclass(frozen=True)
class UserRecord:
    id: str
    email: str
    name: str
    role: str
    active: bool


class UserStore(Protocol):
    def list_users(self) -> list[UserRecord]: ...

    def invite_user(self, email: str, name: str, role: str) -> UserRecord: ...

    def set_role(self, user_id: str, role: str) -> Optional[UserRecord]: ...

    def deactivate(self, user_id: str) -> Optional[UserRecord]: ...


def _row_to_record(row) -> UserRecord:  # type: ignore[no-untyped-def]
    return UserRecord(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"] or "",
        role=row["role"] or ROLE_VIEWER,
        active=not bool(row["banned"]),
    )


class SqlUserStore:
    """Postgres-backed store over Better Auth's ``user`` table."""

    _SELECT = 'SELECT id, email, name, role, banned FROM "user"'

    def list_users(self) -> list[UserRecord]:
        with get_engine().connect() as conn:
            rows = conn.execute(text(f"{self._SELECT} ORDER BY email")).mappings().all()
        return [_row_to_record(row) for row in rows]

    def invite_user(self, email: str, name: str, role: str) -> UserRecord:
        user_id = str(uuid.uuid4())
        with get_engine().begin() as conn:
            conn.execute(
                text(
                    'INSERT INTO "user" (id, email, name, role, "emailVerified", banned, '
                    '"createdAt", "updatedAt") '
                    "VALUES (:id, :email, :name, :role, false, false, now(), now())"
                ),
                {"id": user_id, "email": email, "name": name, "role": role},
            )
        return UserRecord(id=user_id, email=email, name=name, role=role, active=True)

    def set_role(self, user_id: str, role: str) -> Optional[UserRecord]:
        with get_engine().begin() as conn:
            row = conn.execute(
                text(
                    f'UPDATE "user" SET role = :role, "updatedAt" = now() '
                    "WHERE id = :id RETURNING id, email, name, role, banned"
                ),
                {"id": user_id, "role": role},
            ).mappings().first()
        return _row_to_record(row) if row else None

    def deactivate(self, user_id: str) -> Optional[UserRecord]:
        with get_engine().begin() as conn:
            row = conn.execute(
                text(
                    'UPDATE "user" SET banned = true, "banReason" = :reason, "updatedAt" = now() '
                    "WHERE id = :id RETURNING id, email, name, role, banned"
                ),
                {"id": user_id, "reason": "deactivated by admin"},
            ).mappings().first()
        return _row_to_record(row) if row else None


def get_user_store() -> UserStore:
    """FastAPI dependency — overridden with a fake in offline tests."""
    return SqlUserStore()
