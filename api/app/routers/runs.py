"""Runs + replay API (spec C1–C3, C5, C6).

Reads come from the checkpointer only (no duplicate store). Starting a run
(`POST /api/runs`) is Admin/Operator, cost-guarded, audited, and phase-locked
against storefront writes. Replay is Admin/Operator, audited with the source
node, and idempotent-safe (a duplicate while one runs returns the in-flight
reference).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..agents import GLOBAL_MONTHLY_CAP
from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..rbac import require_role
from ..runs import (
    CheckpointerRunPorts,
    CheckpointerRunStarter,
    LogReader,
    NodeNotReached,
    RunService,
    RunStarter,
    SpendReader,
    SpendUnavailable,
    SqlLogReader,
    SqlSpendReader,
    UnknownNode,
    validate_briefs,
)
from ..stream import StreamBroker, broker, heartbeat_event, is_run_log_event

router = APIRouter(prefix="/api/runs", tags=["runs"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))
ReplayAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))
StartAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))


class ReplayBody(BaseModel):
    node: str


class StartBody(BaseModel):
    collection_id: str
    design_id: Optional[str] = None
    briefs: Optional[list[dict[str, Any]]] = None
    #: Locked vocabulary from the contract node — `placement` refuses to infer one.
    design_type: Optional[str] = None


def get_ports() -> CheckpointerRunPorts:
    return CheckpointerRunPorts()


def get_run_service(
    writer: AuditWriter = Depends(get_audit_writer),
    ports: CheckpointerRunPorts = Depends(get_ports),
) -> RunService:
    return RunService(scanner=ports, history=ports, executor=ports, writer=writer)


def get_run_starter() -> RunStarter:
    return CheckpointerRunStarter()


def get_spend_reader() -> SpendReader:
    return SqlSpendReader()


def get_log_reader() -> LogReader:
    return SqlLogReader()


def get_broker() -> StreamBroker:
    return broker


def get_heartbeat_seconds() -> float:
    return 15.0


@router.get("")
def list_runs(
    actor: Actor = ReadAllowed,
    service: RunService = Depends(get_run_service),
    collection: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    date: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    return {"items": service.list_runs(collection=collection, status=status_filter, date=date)}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_run(
    body: StartBody,
    actor: Actor = StartAllowed,
    starter: RunStarter = Depends(get_run_starter),
    spend: SpendReader = Depends(get_spend_reader),
    writer: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Start a new pipeline run (spec C1–C7).

    Refuses when month-to-date spend already meets the global cap (C4) — the
    remedy is to raise the cap in Agents → budget caps, so a refusal is
    actionable rather than a silent overspend. Returns before the graph does any
    work: the run executes off the request thread (C7) and is visible via
    ``GET /api/runs`` immediately.
    """
    if not body.collection_id:
        raise HTTPException(status_code=422, detail="collection_id is required")
    if body.design_type is not None:
        from pipeline.nodes.contract import DESIGN_TYPES

        if body.design_type not in DESIGN_TYPES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"design_type must be one of {', '.join(sorted(DESIGN_TYPES))} "
                    f"— got {body.design_type!r}"
                ),
            )
    brief_errors = validate_briefs(body.briefs)
    if brief_errors:
        raise HTTPException(status_code=422, detail=brief_errors)
    try:
        spent = spend.month_to_date_usd()
    except SpendUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"cannot verify the monthly budget before starting a run: {exc}",
        )
    if spent >= GLOBAL_MONTHLY_CAP:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"monthly budget cap reached (${spent:.2f} of ${GLOBAL_MONTHLY_CAP:.2f}) — "
                "raise the cap in Agents before starting another run"
            ),
        )
    result = starter.start(
        collection_id=body.collection_id,
        design_id=body.design_id,
        briefs=body.briefs,
        design_type=body.design_type,
    )
    writer.record(
        actor_user_id=actor.user_id,
        action="run.start",
        entity_type="run",
        entity_id=result["run_id"],
        before=None,
        after={
            "collection_id": result["collection_id"],
            "design_id": result["design_id"],
            "design_type": body.design_type,
            "hitl": result.get("hitl", {}),
            "spend_usd_before": spent,
        },
    )
    return {
        "run_id": result["run_id"],
        "status": result["status"],
        "collection_id": result["collection_id"],
        "design_id": result["design_id"],
    }


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


@router.get("/{run_id}/logs")
def get_run_logs(
    run_id: str,
    actor: Actor = ReadAllowed,
    service: RunService = Depends(get_run_service),
    reader: LogReader = Depends(get_log_reader),
    node: Optional[str] = Query(default=None),
    level: Optional[str] = Query(default=None),
    since: Optional[str] = Query(default=None, description="ISO timestamp floor"),
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict[str, Any]:
    """Per-node log rows for one run (Viewer+). Empty when the run kept no
    server-side rows (offline runs log in-memory only)."""
    try:
        service.run_detail(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown run")
    if since is not None:
        try:
            datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"since must be an ISO timestamp, got {since!r}",
            )
    return {"items": reader.for_run(run_id, node=node, level=level, since=since, limit=limit)}


@router.get("/{run_id}/logs/stream")
async def stream_run_logs(
    run_id: str,
    request: Request,
    actor: Actor = ReadAllowed,
    stream_broker: StreamBroker = Depends(get_broker),
    heartbeat_seconds: float = Depends(get_heartbeat_seconds),
) -> EventSourceResponse:
    """Live per-node log rows for one run (Viewer+), reusing the SSE broker.

    Same heartbeat/disconnect discipline as ``GET /api/stream/runs`` — only
    ``run.log`` events for this run pass the filter.
    """
    async def generator() -> Any:
        queue = stream_broker.new_subscriber()
        try:
            while True:
                getter = asyncio.ensure_future(queue.get())
                try:
                    done, _pending = await asyncio.wait({getter}, timeout=heartbeat_seconds)
                except asyncio.CancelledError:
                    getter.cancel()
                    raise
                if getter in done:
                    event = getter.result()
                    if is_run_log_event(event, run_id):
                        yield {"event": event["type"], "data": json.dumps(event)}
                    # Other runs' rows and queue deltas pass silently — this
                    # stream carries one run's logs only.
                else:
                    getter.cancel()
                    yield {"event": "heartbeat", "data": json.dumps(heartbeat_event())}
        finally:
            stream_broker.unsubscribe(queue)

    return EventSourceResponse(generator())
