"""SSE endpoint ``GET /api/stream/runs`` (spec C5, backend half).

Authenticated (Viewer+) server-sent events carrying run-status and queue
deltas from the in-process broker, plus periodic heartbeats. UI consumption
is PBI-018; this PBI ships the stream only.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..rbac import require_role
from ..stream import StreamBroker, broker, heartbeat_event

router = APIRouter(prefix="/api/stream", tags=["stream"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))

# Production heartbeat cadence; tests override via app state or a small value.
DEFAULT_HEARTBEAT_SECONDS = 15.0


def get_broker() -> StreamBroker:
    return broker


def get_heartbeat_seconds() -> float:
    return DEFAULT_HEARTBEAT_SECONDS


@router.get("/runs")
async def stream_runs(
    request: Request,
    actor: Actor = ReadAllowed,
    stream_broker: StreamBroker = Depends(get_broker),
    heartbeat_seconds: float = Depends(get_heartbeat_seconds),
) -> EventSourceResponse:
    async def generator() -> Any:
        # NOTE: never wrap an async-generator __anext__ in wait_for — cancelling
        # it terminates the subscription. Race queue.get() against the heartbeat
        # timer instead; both are plain tasks safe to cancel. Disconnects are
        # observed via cancellation (sse-starlette cancels the iterator), NOT
        # via request.is_disconnected() — that awaits a receive message that
        # never arrives while the response is still open (deadlock).
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
                    yield {"event": event["type"], "data": json.dumps(event)}
                else:
                    getter.cancel()
                    yield {"event": "heartbeat", "data": json.dumps(heartbeat_event())}
        finally:
            stream_broker.unsubscribe(queue)

    return EventSourceResponse(generator())
