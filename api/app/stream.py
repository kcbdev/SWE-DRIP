"""SSE live stream broker (spec C5, backend half).

In-process pub/sub: the HITL service and graph runner publish run-status and
queue deltas here; ``GET /api/stream/runs`` pushes them to authenticated
(Viewer+) sessions. Single deployable per ADR-002 — no cross-process broker,
no WebSocket, no UI consumption (PBI-018 owns that).

Event shapes (deltas only — never secrets or full state dumps):

- ``run.status``: ``{"type": "run.status", "run_id": ..., "status": ...}``
  e.g. ``resumed`` after a decision re-enters the graph.
- ``queue.delta``: ``{"type": "queue.delta", "approval_id": ..., "run_id": ...,
  "node": ..., "status": ...}`` — one row changed in the approvals queue
  (decided, reopened, or newly pending).
- ``run.log``: ``{"type": "run.log", "run_id": ..., "node": ..., "level": ...,
  "message": ..., "ts": ...}`` — one per-node log row (PBI-042); the per-run
  logs endpoint serves these filtered by run, the global stream ignores them.
- ``heartbeat``: ``{"type": "heartbeat", "ts": ...}`` — keep-alive only.

Delivery is best-effort per subscriber (bounded queues, slow consumers drop,
never block the publisher or the decision path).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

MAX_QUEUE = 100


class StreamBroker:
    """In-process fan-out: one asyncio.Queue per live subscriber."""

    def __init__(self, maxsize: int = MAX_QUEUE) -> None:
        self._maxsize = maxsize
        self._subscribers: set[asyncio.Queue] = set()

    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        """Yield events for one subscriber until cancelled (disconnect)."""
        queue = self.new_subscriber()
        try:
            while True:
                yield await queue.get()
        finally:
            self.unsubscribe(queue)

    def new_subscriber(self) -> asyncio.Queue:
        """Register a subscriber queue (for heartbeat-racing consumers)."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: dict[str, Any]) -> int:
        """Fan out to all live subscribers; drops for full queues. Returns fan-out."""
        delivered = 0
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
                delivered += 1
            except asyncio.QueueFull:
                continue  # slow consumer drops; never blocks the decision path
        return delivered

    def publish_run_status(self, run_id: str, status: str) -> int:
        return self.publish({"type": "run.status", "run_id": run_id, "status": status})

    def publish_queue_delta(
        self, approval_id: int, run_id: str, node: str, status: str
    ) -> int:
        return self.publish(
            {
                "type": "queue.delta",
                "approval_id": approval_id,
                "run_id": run_id,
                "node": node,
                "status": status,
            }
        )

    def publish_run_log(
        self, run_id: str, node: str, level: str, message: str, ts: str
    ) -> int:
        return self.publish(
            {
                "type": "run.log",
                "run_id": run_id,
                "node": node,
                "level": level,
                "message": message,
                "ts": ts,
            }
        )


def is_run_log_event(event: dict[str, Any], run_id: str) -> bool:
    """True when ``event`` is a log row for ``run_id`` (per-run SSE filter)."""
    return (
        isinstance(event, dict)
        and event.get("type") == "run.log"
        and event.get("run_id") == run_id
    )


def heartbeat_event() -> dict[str, Any]:
    return {"type": "heartbeat", "ts": time.time()}


# Process-wide singleton: the one broker for this deployable.
broker = StreamBroker()
