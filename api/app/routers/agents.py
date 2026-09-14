"""Agents API — roster, routing view, budget caps (FR-17, C4).

GET  /api/agents              — full roster (Viewer+)
GET  /api/agents/{node}       — single agent detail (Viewer+)
PATCH /api/agents/{node}/config — budget cap edit (Admin, cost-impact note required)

Model routing is view-only — changes live in pipeline/routing.py (pipeline-core C3).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, ROLE_VIEWER, Actor
from ..rbac import require_role
from ..agents import (
    AgentInfo,
    GLOBAL_MONTHLY_CAP,
    get_agent_detail,
    get_budget_caps,
    get_roster,
    set_budget_cap,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_VIEWER))
AdminOnly = Depends(require_role(ROLE_ADMIN))


def _agent_to_dict(a: AgentInfo) -> dict[str, Any]:
    return {
        "node": a.node,
        "role": a.role,
        "model": a.model,
        "cap_usd": a.cap_usd,
        "spend_usd": a.spend_usd,
        "routing_edit": "pipeline/routing.py",
    }


@router.get("")
def list_agents(actor: Actor = ReadAllowed) -> list[dict[str, Any]]:
    """Return the full agent roster."""
    return [_agent_to_dict(a) for a in get_roster()]


@router.get("/{node}")
def get_agent(node: str, actor: Actor = ReadAllowed) -> dict[str, Any]:
    """Return detail for a single agent."""
    agent = get_agent_detail(node)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown node: {node}")
    return _agent_to_dict(agent)


class AgentConfigPatch(BaseModel):
    cap_usd: float
    cost_impact_note: str  # required — budget discipline, AGENTS.md §3


@router.patch("/{node}/config")
def patch_agent_config(
    node: str,
    body: AgentConfigPatch,
    actor: Actor = AdminOnly,
    audit: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Update a node's budget cap. Requires Admin + cost-impact note."""
    agent = get_agent_detail(node)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown node: {node}")

    if body.cap_usd < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budget cap must be non-negative",
        )

    # Validate against global monthly cap
    if body.cap_usd > GLOBAL_MONTHLY_CAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Budget cap {body.cap_usd} exceeds global monthly cap {GLOBAL_MONTHLY_CAP}",
        )

    if not body.cost_impact_note.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cost_impact_note is required",
        )

    before_cap = get_budget_caps().get(node, 50.0)
    set_budget_cap(node, body.cap_usd)
    after_cap = get_budget_caps().get(node, 50.0)

    audit.record(
        action="agents.budget_cap.update",
        entity_type="agent",
        entity_id=node,
        before_json={"cap_usd": before_cap, "cost_impact_note": None},
        after_json={"cap_usd": after_cap, "cost_impact_note": body.cost_impact_note},
        actor_user_id=actor.user_id,
    )

    return _agent_to_dict(get_agent_detail(node))
