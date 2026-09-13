"""Audit log read API (spec C3) — Viewer+ may read; export as JSON or CSV.

There is deliberately no write/update/delete endpoint here: writes go through
the designated writer only (``api/app/audit.py`` / the auth hook).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ..audit import AuditFilters, AuditReader, get_audit_reader
from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..rbac import require_role

router = APIRouter(prefix="/api/audit", tags=["audit"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))

CSV_COLUMNS = [
    "id",
    "actor_user_id",
    "created_at",
    "action",
    "entity_type",
    "entity_id",
    "before_json",
    "after_json",
]


@router.get("")
def list_audit(
    actor: Actor = ReadAllowed,
    reader: AuditReader = Depends(get_audit_reader),
    filter_actor: Optional[str] = Query(default=None, alias="actor"),
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = Query(default=500, ge=1, le=5000),
    format: str = Query(default="json", pattern="^(json|csv)$"),
) -> Any:
    filters = AuditFilters(
        actor=filter_actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        start=start,
        end=end,
        limit=limit,
    )
    entries = reader.list_entries(filters)

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    **entry,
                    "before_json": _json_cell(entry.get("before_json")),
                    "after_json": _json_cell(entry.get("after_json")),
                }
            )
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit-log.csv"},
        )

    return entries


def _json_cell(value: Any) -> str:
    if value is None:
        return ""
    import json

    return json.dumps(value, separators=(",", ":"))
