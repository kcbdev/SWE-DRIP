"""Runs + replay API (spec C1–C3, C5, C6).

Reads come from the checkpointer only (no duplicate store). Replay is
Admin/Operator, audited with the source node, and idempotent-safe (a duplicate
while one runs returns the in-flight reference).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..rbac import require_role
from ..runs import CheckpointerRunPorts, NodeNotReached, RunService, UnknownNode

router = APIRouter(prefix="/api/runs", tags=["runs"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))
ReplayAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))


class ReplayBody(BaseModel):
    node: str


def get_ports() -> CheckpointerRunPorts:
    return CheckpointerRunPorts()


def get_run_service(
    writer: AuditWriter = Depends(get_audit_writer),
    ports: CheckpointerRunPorts = Depends(get_ports),
) -> RunService:
    return RunService(scanner=ports, history=ports, executor=ports, writer=writer)


@router.get("")
def list_runs(
    actor: Actor = ReadAllowed,
    service: RunService = Depends(get_run_service),
    collection: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    date: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    return {"items": service.list_runs(collection=collection, status=status_filter, date=date)}


@router.get("/{run_id}")
def get_run(
    run_id: str,
    actor: Actor = ReadAllowed,
    service: RunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return service.run_detail(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown run")


@router.post("/{run_id}/replay")
def replay_run(
    run_id: str,
    body: ReplayBody,
    actor: Actor = ReplayAllowed,
    service: RunService = Depends(get_run_service),
) -> dict[str, Any]:
    try:
        return service.replay(run_id, body.node, actor_user_id=actor.user_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown run")
    except UnknownNode as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except NodeNotReached as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
