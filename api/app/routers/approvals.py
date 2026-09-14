"""Approvals queue API (spec C1/C2/C4/C6).

``GET /api/approvals`` (Viewer+) aggregates live checkpointer interrupts with
the thin index — never a duplicated approval model. ``POST
/api/approvals/{id}/decision`` (Admin/Operator) records the decision, resumes
the paused run exactly once via the service, and audits the decision.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..hitl import HitlAmbiguous, HitlStale, HitlUnknownNode, HitlService, get_hitl_service
from ..rbac import require_role

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))
DecideAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))


class DecisionBody(BaseModel):
    action: Literal["approve", "reject", "regenerate"]
    note: Optional[str] = None
    # Optional disambiguation for multi-candidate gates (e.g.
    # {"approved_cluster_id": "cluster-2"}); the fixed action set is unchanged.
    selection: Optional[dict[str, Any]] = None


@router.get("")
def list_approvals(
    actor: Actor = ReadAllowed,
    service: HitlService = Depends(get_hitl_service),
) -> dict[str, Any]:
    return {"items": service.list_queue()}


@router.post("/{item_id}/decision")
def decide_approval(
    item_id: int,
    body: DecisionBody,
    actor: Actor = DecideAllowed,
    service: HitlService = Depends(get_hitl_service),
) -> dict[str, Any]:
    try:
        return service.decide(
            item_id,
            action=body.action,
            note=body.note,
            selection=body.selection,
            actor_user_id=actor.user_id,
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown approval")
    except (ValueError, HitlAmbiguous, HitlUnknownNode) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except HitlStale as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
