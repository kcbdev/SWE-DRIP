"""Design detail + calibration API (spec C2/C4, read path).

Scores come from the LangGraph checkpointer (source of truth); human
decisions join from ``hitl_approvals`` index rows. No new store, no decision
endpoints here (use the HITL decision API), no rubric changes.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..hitl import (
    CheckpointGateSource,
    GraphRunner,
    HitlStale,
    get_approval_index,
    get_gate_source,
    get_graph_runner,
)
from ..rbac import require_role
from ..designs import calibration_for, design_detail_from_state

router = APIRouter(prefix="/api", tags=["designs"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))


def _detail_or_404(runner: GraphRunner, run_id: str) -> dict[str, Any]:
    try:
        values = runner.get_state_values(run_id)
    except HitlStale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown design")
    if not values:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown design")
    return design_detail_from_state(values, run_id)


@router.get("/designs/{design_id}")
def get_design(
    design_id: str,
    actor: Actor = ReadAllowed,
    runner: GraphRunner = Depends(get_graph_runner),
) -> dict[str, Any]:
    return _detail_or_404(runner, design_id)


@router.get("/designs/{design_id}/calibration")
def get_design_calibration(
    design_id: str,
    actor: Actor = ReadAllowed,
    runner: GraphRunner = Depends(get_graph_runner),
    index=Depends(get_approval_index),
) -> dict[str, Any]:
    detail = _detail_or_404(runner, design_id)
    return calibration_for(detail, index.list_for_run(design_id))


@router.get("/calibration")
def list_calibration(
    actor: Actor = ReadAllowed,
    runner: GraphRunner = Depends(get_graph_runner),
    gates: CheckpointGateSource = Depends(get_gate_source),
    index=Depends(get_approval_index),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Recent designs: live interrupted runs first, then index-known runs."""
    run_ids: list[str] = []
    try:
        for info in gates.list_interrupts():
            if info.run_id not in run_ids:
                run_ids.append(info.run_id)
    except Exception:  # noqa: BLE001 - scan failure degrades to index-only
        pass
    for run_id in index.distinct_run_ids(limit=limit):
        if run_id not in run_ids:
            run_ids.append(run_id)
    items = []
    for run_id in run_ids[:limit]:
        try:
            values = runner.get_state_values(run_id)
        except HitlStale:
            values = {}
        if not values:
            items.append(
                {
                    "design_id": None,
                    "run_id": run_id,
                    "rubric": {"result": None, "scores": None, "rubric_version": None},
                    "human_decisions": [],
                    "agreement": None,
                    "note": "run state unavailable (thread gone/retained) — scores unknown",
                }
            )
            continue
        items.append(
            calibration_for(design_detail_from_state(values, run_id), index.list_for_run(run_id))
        )
    return {"items": items}
