"""Settings API — HITL toggles, brand-lock constants, integrations.

C1: per-node HITL on/off (Admin write, confirmation required)
C2: brand-lock constants (Admin + founder-gated confirmation)
C3: integrations status (Viewer+ read); credentials (Admin write, confirmation)
C5: single config source — same store pipeline reads
C6: Viewer+ read, Admin write
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..rbac import require_role
from ..settings_store import (
    SECRET_CREDENTIAL_FIELDS,
    get_brand,
    get_hitl_flags,
    get_integrations,
    set_brand,
    set_hitl_flags,
    set_integration_credentials,
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
        before={"enabled": before[body.node]},
        after={"enabled": body.enabled},
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
        before=before,
        after=after,
        actor_user_id=actor.user_id,
    )
    return after


# ---------------------------------------------------------------------------
# Integrations
# ---------------------------------------------------------------------------

class IntegrationsPatch(BaseModel):
    """Credential patch. Omitted fields are unchanged; "" clears a field."""

    fourthwall_mcp_url: Optional[str] = None
    fourthwall_mcp_token: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: Optional[str] = None
    confirm: bool  # must be true — Admin confirmation required


def _presence_only(status_payload: dict[str, Any]) -> dict[str, bool]:
    """Strip non-secret endpoints for the audit row (never log secrets)."""
    return {
        "fourthwall_mcp": bool(status_payload.get("fourthwall_mcp")),
        "openrouter": bool(status_payload.get("openrouter")),
    }


@router.get("/integrations")
def get_integrations_status(actor: Actor = ReadAllowed) -> dict[str, Any]:
    """Return integration status + non-secret endpoint hints.

    Secret fields (tokens/keys) are NEVER returned — presence booleans only.
    """
    payload = get_integrations()
    for secret in SECRET_CREDENTIAL_FIELDS:
        payload.pop(secret, None)
    return payload


@router.patch("/integrations")
def patch_integrations(
    body: IntegrationsPatch,
    actor: Actor = AdminOnly,
    audit: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Set Fourthwall/OpenRouter credentials. Admin-only; confirmation required.

    Values are stored in the settings store and take precedence over the
    deployment env vars. Audit records presence changes only.
    """
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required to update integration credentials",
        )
    before = get_integrations()
    patch = {
        key: value
        for key, value in body.model_dump(exclude={"confirm"}).items()
        if value is not None
    }
    if not patch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No credential fields supplied",
        )
    set_integration_credentials(patch)
    after = get_integrations()
    audit.record(
        action="settings.integrations.update",
        entity_type="settings",
        entity_id="integrations",
        before=_presence_only(before),
        after=_presence_only(after),
        actor_user_id=actor.user_id,
    )
    return get_integrations_status(actor)


@router.post("/integrations/test")
def test_integrations(actor: Actor = AdminOnly) -> dict[str, Any]:
    """Probe the Fourthwall MCP with the configured credentials.

    Returns ``{"ok": true}`` or ``{"ok": false, "error": "..."}`` — a degraded
    read is a normal outcome, never a 500. No credential values are echoed.
    """
    from ..fourthwall.client import FourthwallError, FourthwallReadClient
    from ..settings_store import resolve_integration

    url = resolve_integration("fourthwall_mcp_url")
    token = resolve_integration("fourthwall_mcp_token")
    if not url or not token:
        return {"ok": False, "error": "Fourthwall MCP URL and token are not both configured"}
    client = FourthwallReadClient(url=url, token=token, timeout=10.0)
    try:
        client.list_products(limit=1)
    except FourthwallError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True}
