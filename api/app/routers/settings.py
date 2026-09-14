"""Settings API — HITL toggles, brand-lock constants, integrations status.

C1: per-node HITL on/off (Admin write, confirmation required)
C2: brand-lock constants (Admin + founder-gated confirmation)
C3: integrations presence-only (Viewer+ read)
C5: single config source — same store pipeline reads
C6: Viewer+ read, Admin write
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..rbac import require_role
from ..settings_store import (
    get_brand,
    get_hitl_flags,
    get_integrations,
    set_brand,
    set_hitl_flags,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))
AdminOnly = Depends(require_role(ROLE_ADMIN))


# ---------------------------------------------------------------------------
# HITL
# ---------------------------------------------------------------------------

class HitlPatch(BaseModel):
    node: str
    enabled: bool
    confirm: bool  # must be true — UI confirmation required


@router.get("/hitl")
def get_hitl(actor: Actor = ReadAllowed) -> dict[str, bool]:
    """Return HITL flag state for all nodes."""
    return get_hitl_flags()


@router.patch("/hitl")
def patch_hitl(
    body: HitlPatch,
    actor: Actor = AdminOnly,
    audit: AuditWriter = Depends(get_audit_writer),
) -> dict[str, bool]:
    """Toggle a single node's HITL flag. Requires confirmation."""
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required to toggle HITL gate",
        )
    flags = get_hitl_flags()
    if body.node not in flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown node: {body.node}",
        )
    before = flags.copy()
    set_hitl_flags({body.node: body.enabled})
    after = get_hitl_flags()
    audit.record(
        action="settings.hitl.toggle",
        entity_type="settings",
        entity_id=body.node,
        before_json={"enabled": before[body.node]},
        after_json={"enabled": body.enabled},
        actor_user_id=actor.user_id,
    )
    return after


# ---------------------------------------------------------------------------
# Brand-lock constants
# ---------------------------------------------------------------------------

class BrandPatch(BaseModel):
    palette: dict[str, str] | None = None
    typeface: str | None = None
    forbidden: list[str] | None = None
    confirm: bool  # must be true — founder-gated confirmation required


@router.get("/brand")
def get_brand_constants(actor: Actor = ReadAllowed) -> dict[str, Any]:
    """Return brand-lock constants (palette, typeface, forbidden elements)."""
    return get_brand()


@router.patch("/brand")
def patch_brand(
    body: BrandPatch,
    actor: Actor = AdminOnly,
    audit: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Edit brand-lock constants. Requires Admin + confirmation. Audit-logged."""
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required to edit brand-lock constants",
        )
    before = get_brand()
    patch: dict[str, Any] = {}
    if body.palette is not None:
        patch["palette"] = body.palette
    if body.typeface is not None:
        patch["typeface"] = body.typeface
    if body.forbidden is not None:
        patch["forbidden"] = body.forbidden
    set_brand(patch)
    after = get_brand()
    audit.record(
        action="settings.brand.update",
        entity_type="settings",
        entity_id="brand",
        before_json=before,
        after_json=after,
        actor_user_id=actor.user_id,
    )
    return after


# ---------------------------------------------------------------------------
# Integrations status (read-only)
# ---------------------------------------------------------------------------

@router.get("/integrations")
def get_integrations_status(actor: Actor = ReadAllowed) -> dict[str, bool]:
    """Return configured/not-configured status for integrations.

    Presence only — never exposes secret values.
    """
    return get_integrations()
