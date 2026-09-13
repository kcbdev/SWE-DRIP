"""Audit log — the single write path (spec C1, C2) and the read path (C3, C5).

Writers: API endpoints use ``get_audit_writer``; the Better Auth hook in
``control-panel/lib/audit.ts`` writes auth events to the same table. The row
shape (``actor_user_id, created_at, action, entity_type, entity_id,
before_json, after_json``) is the shared contract — see
``api/migrations/0001_audit_log.sql``.

``build_audit_row`` and ``build_audit_query`` are pure so they are unit-testable
offline; only ``SqlAuditWriter`` / ``SqlAuditReader`` touch the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol

from sqlalchemy import Select, select
from sqlalchemy.sql import ColumnElement

from .db import get_engine
from .models import audit_log

# Explicit principal for system-initiated writes — never null by accident (C2).
SYSTEM_ACTOR = "system"


@dataclass(frozen=True)
class AuditFilters:
    actor: Optional[str] = None
    action: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    limit: int = 500


def build_audit_row(
    *,
    actor_user_id: str,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    before: Any = None,
    after: Any = None,
) -> dict[str, Any]:
    """Validate and shape an audit row (pure). Raises if actor or keys are missing."""
    if not actor_user_id:
        raise ValueError("actor_user_id is required; use SYSTEM_ACTOR explicitly")
    if not action or not entity_type:
        raise ValueError("action and entity_type are required")
    return {
        "actor_user_id": actor_user_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before_json": before,
        "after_json": after,
    }


def build_audit_query(filters: AuditFilters) -> Select:
    """Compose the read query from filters (pure; no execution)."""
    conditions: list[ColumnElement[bool]] = []
    if filters.actor:
        conditions.append(audit_log.c.actor_user_id == filters.actor)
    if filters.action:
        conditions.append(audit_log.c.action == filters.action)
    if filters.entity_type:
        conditions.append(audit_log.c.entity_type == filters.entity_type)
    if filters.entity_id:
        conditions.append(audit_log.c.entity_id == filters.entity_id)
    if filters.start:
        conditions.append(audit_log.c.created_at >= filters.start)
    if filters.end:
        conditions.append(audit_log.c.created_at <= filters.end)

    stmt = select(audit_log)
    if conditions:
        stmt = stmt.where(*conditions)
    return stmt.order_by(audit_log.c.created_at.desc()).limit(filters.limit)


class AuditWriter(Protocol):
    def record(
        self,
        *,
        actor_user_id: str,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        before: Any = None,
        after: Any = None,
    ) -> None: ...


class AuditReader(Protocol):
    def list_entries(self, filters: AuditFilters) -> list[dict[str, Any]]: ...


class SqlAuditWriter:
    def record(
        self,
        *,
        actor_user_id: str,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        before: Any = None,
        after: Any = None,
    ) -> None:
        row = build_audit_row(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
        )
        with get_engine().begin() as conn:
            conn.execute(audit_log.insert().values(**row))


def _serialize(row: Any) -> dict[str, Any]:
    data = dict(row)
    created = data.get("created_at")
    if isinstance(created, datetime):
        data["created_at"] = created.isoformat()
    return data


class SqlAuditReader:
    def list_entries(self, filters: AuditFilters) -> list[dict[str, Any]]:
        with get_engine().connect() as conn:
            rows = conn.execute(build_audit_query(filters)).mappings().all()
        return [_serialize(row) for row in rows]


def get_audit_writer() -> AuditWriter:
    return SqlAuditWriter()


def get_audit_reader() -> AuditReader:
    return SqlAuditReader()
