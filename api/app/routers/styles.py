"""Styles management API (PBI-056, spec C1).

Reads are Viewer+; creates/edits are Admin-only and audited. The locked
repo only grows: DELETE is a loud 405 (deletion would strand approved
contracts). Every write carries the C1 revalidation report.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, ROLE_VIEWER, Actor
from ..collections_store import get_collections_store
from ..rbac import require_role
from ..styles_store import (
    DuplicateStyle,
    RepoMissing,
    StylesStore,
    UnknownStyle,
    VersionConflict,
    get_styles_store,
)

router = APIRouter(prefix="/api/styles", tags=["styles"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_VIEWER))
AdminOnly = Depends(require_role(ROLE_ADMIN))


class StyleCreateBody(BaseModel):
    name: str
    graphic_definition: str
    expected_version: int


class StyleUpdateBody(BaseModel):
    name: Optional[str] = None
    graphic_definition: Optional[str] = None
    expected_version: int


def _with_report(doc: dict[str, Any], collections) -> dict[str, Any]:
    """Attach the C1 revalidation report (never silent, possibly empty)."""
    try:
        contracts = [r["contract"] for r in collections.list()]
    except Exception:  # noqa: BLE001 - report degrades, the write stands
        contracts = []
    names = [s["name"] for s in doc["styles"]]
    affected = StylesStore.revalidate(contracts, names)
    return {**doc, "affected_contracts": affected}


@router.get("")
def list_styles(
    actor: Actor = ReadAllowed,
    store: StylesStore = Depends(get_styles_store),
) -> dict[str, Any]:
    """Version + locked entries (Viewer+). Missing repo is a loud 503."""
    try:
        return store.read()
    except RepoMissing as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_style(
    body: StyleCreateBody,
    actor: Actor = AdminOnly,
    store: StylesStore = Depends(get_styles_store),
    collections=Depends(get_collections_store),
    writer: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Append a style (Admin, audited): 409 on duplicate/stale version."""
    try:
        doc = store.create(body.name, body.graphic_definition, body.expected_version)
    except RepoMissing as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except DuplicateStyle as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except VersionConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    result = _with_report(doc, collections)
    writer.record(
        actor_user_id=actor.user_id,
        action="styles.create",
        entity_type="style",
        entity_id=body.name.strip(),
        before=None,
        after={"name": body.name.strip(), "version": doc["version"],
               "affected_contracts": result["affected_contracts"]},
    )
    return result


@router.patch("/{name}")
def update_style(
    name: str,
    body: StyleUpdateBody,
    actor: Actor = AdminOnly,
    store: StylesStore = Depends(get_styles_store),
    collections=Depends(get_collections_store),
    writer: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Rename and/or redefine a style (Admin, audited)."""
    try:
        before = store.read()
    except RepoMissing as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    try:
        doc = store.update(name, body.name, body.graphic_definition, body.expected_version)
    except UnknownStyle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown style {name!r}")
    except DuplicateStyle as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except VersionConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    result = _with_report(doc, collections)
    writer.record(
        actor_user_id=actor.user_id,
        action="styles.update",
        entity_type="style",
        entity_id=name,
        before={"version": before["version"]},
        after={"version": doc["version"], "affected_contracts": result["affected_contracts"]},
    )
    return result


@router.delete("/{name}", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
def delete_style(name: str, actor: Actor = AdminOnly) -> dict[str, Any]:
    """Refused loudly: the locked repo only grows (PBI-056)."""
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="styles cannot be deleted — the locked repo only grows; rename instead",
    )
