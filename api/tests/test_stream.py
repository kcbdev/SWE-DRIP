"""SSE live stream contracts (spec C5, backend half; offline)."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.auth import ROLE_VIEWER, Actor, get_current_actor
from api.app.routers import stream as stream_router
from api.app.stream import StreamBroker, broker, heartbeat_event


def _app(test_broker: StreamBroker, heartbeat_seconds: float = 0.05) -> FastAPI:
    app = FastAPI()
    app.include_router(stream_router.router)
    app.dependency_overrides[get_current_actor] = lambda: Actor("u-9", "op@x.y", ROLE_VIEWER)
    app.dependency_overrides[stream_router.get_broker] = lambda: test_broker
    app.dependency_overrides[stream_router.get_heartbeat_seconds] = lambda: heartbeat_seconds
    return app


def _parse_sse(payload: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    name = ""
    for line in payload.splitlines():
        if line.startswith("event:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            events.append((name, json.loads(line.split(":", 1)[1].strip())))
            name = ""
    return events


# ------------------------------------------------------------------ broker


def test_broker_publish_subscribe_in_order() -> None:
    async def scenario() -> list[dict]:
        test_broker = StreamBroker()
        received: list[dict] = []

        async def consumer() -> None:
            async for event in test_broker.subscribe():
                received.append(event)
                if len(received) == 2:
                    break

        task = asyncio.ensure_future(consumer())
        await asyncio.sleep(0)  # let the subscriber register
        test_broker.publish_run_status("run-1", "resumed")
        test_broker.publish_queue_delta(7, "run-1", "publish_gate", "approved")
        await asyncio.wait_for(task, timeout=2)
        return received

    received = asyncio.run(scenario())
    assert received[0] == {"type": "run.status", "run_id": "run-1", "status": "resumed"}
    assert received[1]["type"] == "queue.delta" and received[1]["approval_id"] == 7


def test_broker_slow_consumer_drops_never_blocks() -> None:
    test_broker = StreamBroker(maxsize=1)
    queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    queue.put_nowait({"type": "stale"})
    test_broker._subscribers.add(queue)
    try:
        assert test_broker.publish({"type": "run.status"}) == 0  # full → dropped
    finally:
        test_broker._subscribers.discard(queue)


def test_event_shapes_carry_deltas_only() -> None:
    assert set(heartbeat_event()) == {"type", "ts"}
    delta = StreamBroker().publish_queue_delta(1, "r", "n", "approved")
    assert delta == 0  # no subscribers; shape asserted in the order test


# ---------------------------------------------------------------- endpoint


async def _read_sse_lines(response, limit: int, timeout: float = 10.0) -> list[str]:
    """Read up to `limit` non-blank SSE lines with an overall timeout."""
    lines: list[str] = []
    try:
        async with asyncio.timeout(timeout):
            async for line in response.aiter_lines():
                if line.strip():
                    lines.append(line)
                if len(lines) >= limit:
                    break
    except TimeoutError:
        pass
    return lines


class LiveServer:
    """Real uvicorn server in a thread: the only honest way to test an
    infinite SSE stream (TestClient buffers responses; ASGI-transport
    streaming hangs under sse-starlette's task group)."""

    def __init__(self, app: FastAPI) -> None:
        import uvicorn

        self._config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
        self._server = uvicorn.Server(self._config)
        self._thread: object = None

    async def __aenter__(self) -> str:
        import threading

        thread = threading.Thread(target=self._server.run, daemon=True)
        thread.start()
        while not self._server.started:
            await asyncio.sleep(0.02)
        port = self._server.servers[0].sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    async def __aexit__(self, *args: object) -> None:
        self._server.should_exit = True


async def test_client_receives_events_in_order() -> None:
    import httpx

    test_broker = StreamBroker()
    async with LiveServer(_app(test_broker, heartbeat_seconds=30.0)) as base:
        async with httpx.AsyncClient(base_url=base) as client:
            received: list[str] = []

            async def publish_soon() -> None:
                await asyncio.sleep(0.3)
                test_broker.publish_run_status("run-1", "resumed")
                test_broker.publish_queue_delta(3, "run-1", "contract_approval", "approved")

            task = asyncio.ensure_future(publish_soon())
            try:
                async with client.stream("GET", "/api/stream/runs") as response:
                    assert response.status_code == 200
                    received = await _read_sse_lines(response, 4)
            finally:
                await task
    assert any('"run.status"' in line for line in received)
    assert any('"queue.delta"' in line for line in received)


async def test_heartbeat_emitted_without_events() -> None:
    import httpx

    test_broker = StreamBroker()
    async with LiveServer(_app(test_broker, heartbeat_seconds=0.01)) as base:
        async with httpx.AsyncClient(base_url=base) as client:
            async with client.stream("GET", "/api/stream/runs") as response:
                assert response.status_code == 200
                lines = await _read_sse_lines(response, 2)
    assert any(line.startswith("event: heartbeat") for line in lines)


def test_unauthenticated_stream_rejected() -> None:
    app = FastAPI()
    app.include_router(stream_router.router)
    assert TestClient(app).get("/api/stream/runs").status_code == 401


def test_decision_publishes_deltas() -> None:
    """The HITL publish hook fans out queue.delta + run.status (best-effort)."""
    from api.app.hitl import _publish_decision_events

    test_broker = StreamBroker()
    received: list[dict] = []
    original = broker.publish

    async def scenario() -> None:
        async def consumer() -> None:
            async for event in test_broker.subscribe():
                received.append(event)
                if len(received) == 2:
                    break

        task = asyncio.ensure_future(consumer())
        await asyncio.sleep(0)
        # Patch the singleton path used by the hook.
        import api.app.hitl as hitl_module
        import api.app.stream as stream_module

        saved = stream_module.broker
        stream_module.broker = test_broker
        try:
            hitl_module._publish_decision_events(9, run_id="run-9", node="publish_gate", status="approved")
        finally:
            stream_module.broker = saved
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(scenario())
    kinds = [event["type"] for event in received]
    assert kinds == ["queue.delta", "run.status"]
