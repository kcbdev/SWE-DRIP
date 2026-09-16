"""Operator token issuance + revocation (Admin-only, audited).

The plaintext token appears exactly once — in the issue response. Every other
surface (list rows, audit rows, errors) carries the ``prefix`` only.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, Actor
from ..db import get_engine
from ..operator_tokens import SCOPE_OPERATE, SCOPE_READ, SCOPES, issue_token, list_tokens, revoke_token
from ..rbac import require_role

router = APIRouter(prefix="/api/operator-tokens", tags=["operator-tokens"])

AdminOnly = Depends(require_role(ROLE_ADMIN))


class IssueBody(BaseModel):
    name: str
    scopes: list[str] = [SCOPE_READ]


@router.post("", status_code=status.HTTP_201_CREATED)
def issue_operator_token(
    body: IssueBody,
    actor: Actor = AdminOnly,
    audit: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Issue a token. Admin-only; the value is shown here once, then never again."""
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="token name is required")
    unknown = [s for s in body.scopes if s not in SCOPES]
    if unknown or not body.scopes:
        raise HTTPException(
            status_code=400,
            detail=f"scopes must be a non-empty subset of {list(SCOPES)!r}",
        )
    try:
        plaintext, meta = issue_token(
            get_engine(), name=body.name.strip(),
            scopes=list(body.scopes), actor_user_id=actor.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit.record(
        action="operator_token.issue",
        entity_type="operator_token",
        entity_id=meta["prefix"],
        before=None,
        after={"prefix": meta["prefix"], "name": meta["name"], "scopes": meta["scopes"]},
        actor_user_id=actor.user_id,
    )
    return {**meta, "token": plaintext}


@router.get("")
def list_operator_tokens(actor: Actor = AdminOnly) -> dict[str, Any]:
    """Token metadata (Admin-only). Hashes never leave the store."""
    return {"items": list_tokens(get_engine())}


@router.post("/{token_id}/revoke")
def revoke_operator_token(
    token_id: int,
    actor: Actor = AdminOnly,
    audit: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Flag a token revoked (Admin-only, audited). Unknown ids 404."""
    # Resolve the prefix for the audit row without disclosing the hash.
    known = {row["id"]: row["prefix"] for row in list_tokens(get_engine())}
    if token_id not in known:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown token")
    if not revoke_token(get_engine(), token_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="token already revoked")
    audit.record(
        action="operator_token.revoke",
        entity_type="operator_token",
        entity_id=known[token_id],
        before={"revoked": False},
        after={"revoked": True},
        actor_user_id=actor.user_id,
    )
    return {"id": token_id, "prefix": known[token_id], "revoked": True}
