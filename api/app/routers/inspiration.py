"""Inspiration ingest API (spec C3).

Admin writes (audited), Viewer+ reads. One POST handles both shapes by
content type: multipart file uploads and JSON link refs. Bytes are served
same-origin for board display; values never echo beyond the served bytes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import ValidationError

from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, ROLE_VIEWER, Actor
from ..collections_store import CollectionNotFound
from ..inspiration import MAX_BYTES, InspirationStore, resolve_collections_root
from ..rbac import require_role

router = APIRouter(prefix="/api/collections", tags=["inspiration"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_VIEWER))
AdminOnly = Depends(require_role(ROLE_ADMIN))


def get_inspiration_store() -> InspirationStore:
    return InspirationStore(resolve_collections_root())


@router.get("/{slug}/inspiration")
def list_inspiration(
    slug: str,
    actor: Actor = ReadAllowed,
    store: InspirationStore = Depends(get_inspiration_store),
) -> dict[str, Any]:
    """Assets + link refs for one collection (Viewer+)."""
    try:
        return store.list(slug)
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{slug}/inspiration", status_code=status.HTTP_201_CREATED)
async def add_inspiration(
    slug: str,
    request: Request,
    actor: Actor = AdminOnly,
    store: InspirationStore = Depends(get_inspiration_store),
    audit: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Attach inspiration: multipart image (file + optional note/source_url
    fields) or JSON link ref ({url, note}). Admin-only, audited."""
    content_type = request.headers.get("content-type", "")
    try:
        if content_type.startswith("multipart/"):
            # Declared-size gate first: never buffer an admittedly oversize
            # body. The bounded read below caps actual memory at MAX+1.
            try:
                declared = int(request.headers.get("content-length") or 0)
            except ValueError:
                declared = 0
            if declared > MAX_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=f"image exceeds {MAX_BYTES} bytes",
                )
            form = await request.form()
            upload = form.get("file")
            if upload is None or not hasattr(upload, "read"):
                raise HTTPException(status_code=400, detail="multipart body needs a file part")
            content = await upload.read(MAX_BYTES + 1)  # type: ignore[union-attr]
            record = store.add_asset(
                slug,
                content,
                str(getattr(upload, "content_type", "") or ""),
                note=str(form.get("note") or ""),
                source_url=str(form.get("source_url") or ""),
                actor_user_id=actor.user_id,
            )
            audit.record(
                action="inspiration.asset.add",
                entity_type="collection",
                entity_id=slug,
                before=None,
                after={"id": record["id"], "filename": record["filename"],
                       "size_bytes": record["size_bytes"]},
                actor_user_id=actor.user_id,
            )
            return record
        if content_type.startswith("application/json"):
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="JSON body must be an object")
            entry = store.add_link(
                slug, str(payload.get("url") or ""), str(payload.get("note") or ""))
            audit.record(
                action="inspiration.link.add",
                entity_type="collection",
                entity_id=slug,
                before=None,
                after=entry,
                actor_user_id=actor.user_id,
            )
            return entry
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="send multipart image bytes or a JSON link ref",
        )
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False))


@router.get("/{slug}/inspiration/{asset_id}/file")
def serve_inspiration_file(
    slug: str,
    asset_id: str,
    actor: Actor = ReadAllowed,
    store: InspirationStore = Depends(get_inspiration_store),
) -> Response:
    """Same-origin byte serving for board display (Viewer+)."""
    try:
        content, media_type = store.read_bytes(slug, asset_id)
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown asset")
    return Response(content=content, media_type=media_type)


@router.delete("/{slug}/inspiration/{asset_id}")
def delete_inspiration(
    slug: str,
    asset_id: str,
    actor: Actor = AdminOnly,
    store: InspirationStore = Depends(get_inspiration_store),
    audit: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Remove bytes + sidecar (Admin-only, audited)."""
    try:
        removed = store.delete(slug, asset_id)
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown asset")
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown asset")
    audit.record(
        action="inspiration.asset.delete",
        entity_type="collection",
        entity_id=slug,
        before={"id": asset_id},
        after=None,
        actor_user_id=actor.user_id,
    )
    return {"id": asset_id, "deleted": True}
