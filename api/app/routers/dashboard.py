"""Dashboard summary endpoint (Viewer+ read; no writes)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..audit import AuditFilters, AuditReader, get_audit_reader
from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..dashboard import (
    ACTIVITY_LIMIT,
    CostReader,
    CollectionsReader,
    PendingApprovalsReader,
    _safe,
    build_summary,
    get_collections_reader,
    get_cost_reader,
    get_pending_approvals_reader,
)
from ..rbac import require_role

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))


@router.get("/summary")
def summary(
    actor: Actor = ReadAllowed,
    audit: AuditReader = Depends(get_audit_reader),
    costs: CostReader = Depends(get_cost_reader),
    collections: CollectionsReader = Depends(get_collections_reader),
    pending: PendingApprovalsReader = Depends(get_pending_approvals_reader),
) -> dict[str, Any]:
    spend_rows, _ = _safe(costs.month_rows)
    contracts, _ = _safe(collections.contracts)
    audit_entries, _ = _safe(
        lambda: audit.list_entries(AuditFilters(limit=ACTIVITY_LIMIT))
    )
    pending_items, _ = _safe(pending.items)
    return build_summary(
        spend_rows=spend_rows,
        contracts=contracts,
        audit_entries=audit_entries,
        pending=pending_items,
    )
