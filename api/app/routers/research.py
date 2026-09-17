"""Research-run API (PBI-055, spec C4/C6).

Trigger + inspection for the collection-research graph. Reads come from the
checkpointer only (no duplicate store); starting is Admin/Operator,
cost-guarded, and audited. Gate decisions reuse the shared HITL service
wired to research gates — no second approval model.
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
from ..collections_store import CollectionNotFound
from ..hitl import HitlService, get_approval_index
from ..rbac import require_role
from ..research_runs import (
    ResearchGraphRunner,
    ResearchRunPorts,
    ResearchRunStarter,
    list_research_runs,
    research_run_detail,
)
from ..runs import LogReader, SpendReader, SpendUnavailable, SqlLogReader, SqlSpendReader
from ..stream import StreamBroker, broker, heartbeat_event, is_run_log_event
from .approvals import DecisionBody

router = APIRouter(prefix="/api/research", tags=["research"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))
StartAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))
DecideAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))


class ResearchStartBody(BaseModel):
    collection_slug: str


def get_research_ports() -> ResearchRunPorts:
    return ResearchRunPorts()


def get_research_starter() -> ResearchRunStarter:
    return ResearchRunStarter()


def get_research_runner() -> ResearchGraphRunner:
    return ResearchGraphRunner()


def get_spend_reader() -> SpendReader:
    return SqlSpendReader()


def get_log_reader() -> LogReader:
    return SqlLogReader()


def get_broker() -> StreamBroker:
    return broker


def get_heartbeat_seconds() -> float:
    return 15.0


def get_research_gates():
    from pipeline.collection_graph import RESEARCH_RUN_PREFIX, build_collection_graph

    from ..hitl import CheckpointerGateSource

    return CheckpointerGateSource(
        graph_factory=build_collection_graph,
        thread_filter=lambda thread_id: thread_id.startswith(RESEARCH_RUN_PREFIX))


def get_research_service(
    gates=Depends(get_research_gates),
    index=Depends(get_approval_index),
    runner: ResearchGraphRunner = Depends(get_research_runner),
    writer: AuditWriter = Depends(get_audit_writer),
) -> HitlService:
    return HitlService(gates=gates, index=index, runner=runner, writer=writer)


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
def start_research_run(
    body: ResearchStartBody,
    actor: Actor = StartAllowed,
    starter: ResearchRunStarter = Depends(get_research_starter),
    spend: SpendReader = Depends(get_spend_reader),
    writer: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Start a collection-research run (spec C4).

    Same discipline as item runs: cost-guarded, audited, off-thread with an
    immediately visible record. Refuses with 422 when the draft has nothing
    curated (the review node would fail loudly — the trigger says so first).
    """
    if not (body.collection_slug or "").strip():
        raise HTTPException(status_code=422, detail="collection_slug is required")
    try:
        spent = spend.month_to_date_usd()
    except SpendUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"cannot verify the monthly budget before starting research: {exc}",
        )
    if spent >= GLOBAL_MONTHLY_CAP:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"monthly budget cap reached (${spent:.2f} of ${GLOBAL_MONTHLY_CAP:.2f}) — "
                "raise the cap in Agents before starting another run"
            ),
        )
    try:
        result = starter.start(collection_slug=body.collection_slug, actor_user_id=actor.user_id)
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    writer.record(
        actor_user_id=actor.user_id,
        action="research.start",
        entity_type="research_run",
        entity_id=result["run_id"],
        before=None,
        after={"collection_slug": result["collection_slug"], "spend_usd_before": spent},
    )
    return result


@router.get("/runs")
def list_research(
    actor: Actor = ReadAllowed,
    ports: ResearchRunPorts = Depends(get_research_ports),
) -> dict[str, Any]:
    return {"items": list_research_runs(ports)}


@router.get("/runs/{run_id}")
def get_research_run(
    run_id: str,
    actor: Actor = ReadAllowed,
    ports: ResearchRunPorts = Depends(get_research_ports),
) -> dict[str, Any]:
    try:
        return research_run_detail(ports, run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown research run")


@router.get("/runs/{run_id}/logs")
def get_research_logs(
    run_id: str,
    actor: Actor = ReadAllowed,
    ports: ResearchRunPorts = Depends(get_research_ports),
    reader: LogReader = Depends(get_log_reader),
    node: Optional[str] = Query(default=None),
    level: Optional[str] = Query(default=None),
    since: Optional[str] = Query(default=None, description="ISO timestamp floor"),
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict[str, Any]:
    try:
        research_run_detail(ports, run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown research run")
    if since is not None:
        try:
            datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"since must be an ISO timestamp, got {since!r}",
            )
    return {"items": reader.for_run(run_id, node=node, level=level, since=since, limit=limit)}


@router.get("/runs/{run_id}/logs/stream")
async def stream_research_logs(
    run_id: str,
    request: Request,
    actor: Actor = ReadAllowed,
    stream_broker: StreamBroker = Depends(get_broker),
    heartbeat_seconds: float = Depends(get_heartbeat_seconds),
) -> EventSourceResponse:
    """Live per-node log rows for one research run (Viewer+)."""

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
                else:
                    getter.cancel()
                    yield {"event": "heartbeat", "data": json.dumps(heartbeat_event())}
        finally:
            stream_broker.unsubscribe(queue)

    return EventSourceResponse(generator())


@router.get("/approvals")
def list_research_approvals(
    actor: Actor = ReadAllowed,
    service: HitlService = Depends(get_research_service),
) -> dict[str, Any]:
    """Open research gates (Viewer+): draft + board + diversity flags payloads."""
    return {"items": service.list_queue()}


@router.post("/approvals/{item_id}/decision")
def decide_research_approval(
    item_id: int,
    body: DecisionBody,
    actor: Actor = DecideAllowed,
    service: HitlService = Depends(get_research_service),
) -> dict[str, Any]:
    """Decide a research gate: approve / reject / regenerate, or approve with
    ``selection.contract`` for edit-and-approve (Admin/Operator, audited)."""
    from ..hitl import HitlAmbiguous, HitlStale, HitlUnknownNode

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
