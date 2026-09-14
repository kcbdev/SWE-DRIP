"""Collections CRUD API (spec C1/C2/C5/C6).

YAML files are the single source (``CollectionsStore``); Postgres stores
nothing. Reads are Viewer+; create/edit are Admin-only. Status transitions
are the lifecycle's job (PBI-020) — PATCH rejects them. Every mutation writes
an audit row through the shared writer.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..collections_store import (
    CollectionExists,
    CollectionNotFound,
    CollectionsStore,
    MtimeConflict,
    get_collections_store,
)
from ..rbac import require_role

router = APIRouter(prefix="/api/collections", tags=["collections"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))
AdminOnly = Depends(require_role(ROLE_ADMIN))

STATUSES = ("draft", "active", "retired")


def _detail(record: dict[str, Any]) -> dict[str, Any]:
    return {"id": record["contract"]["collection_id"], **record}


@router.get("")
def list_collections(
    actor: Actor = ReadAllowed,
    store: CollectionsStore = Depends(get_collections_store),
    status_filter: Optional[str] = Query(default=None, alias="status"),
) -> dict[str, Any]:
    if status_filter is not None and status_filter not in STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {STATUSES!r}")
    return {"items": [_detail(record) for record in store.list(status=status_filter)]}


@router.get("/{slug}")
def get_collection(
    slug: str,
    actor: Actor = ReadAllowed,
    store: CollectionsStore = Depends(get_collections_store),
) -> dict[str, Any]:
    try:
        return _detail(store.get(slug))
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: dict[str, Any],
    actor: Actor = AdminOnly,
    store: CollectionsStore = Depends(get_collections_store),
    writer: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    payload = {**payload, "status": "draft"}  # creates are always drafts
    try:
        record = store.create(payload)
    except CollectionExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_errors(exc))
    writer.record(
        actor_user_id=actor.user_id,
        action="collection.create",
        entity_type="collection",
        entity_id=record["contract"]["collection_id"],
        before=None,
        after=record["contract"],
    )
    return _detail(record)


@router.patch("/{slug}")
def update_collection(
    slug: str,
    payload: dict[str, Any],
    actor: Actor = AdminOnly,
    store: CollectionsStore = Depends(get_collections_store),
    writer: AuditWriter = Depends(get_audit_writer),
    expected_mtime: Optional[float] = Query(default=None),
) -> dict[str, Any]:
    try:
        before = store.get(slug)["contract"]
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    try:
        record = store.update(slug, payload, expected_mtime=expected_mtime)
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    except MtimeConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=_errors(exc))
    writer.record(
        actor_user_id=actor.user_id,
        action="collection.update",
        entity_type="collection",
        entity_id=slug,
        before=before,
        after=record["contract"],
    )
    return _detail(record)


def _errors(exc: BaseException) -> list[dict[str, Any]]:
    if isinstance(exc, ValidationError):
        return exc.errors(include_url=False)
    return [{"type": "value_error", "loc": (), "msg": str(exc)}]
