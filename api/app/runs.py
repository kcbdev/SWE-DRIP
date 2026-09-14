"""Runs inspection + replay over the LangGraph checkpointer (spec C1–C3, C5, C6).

No duplicate run-state store (NFR-1): listing, per-node detail, and replay all
read the checkpointer. Replay uses the checkpointer's resume-from-state
capability (``update_state(..., as_node=node)`` + invoke) — no custom re-run
engine. Node display order is the locked ``NODE_ORDER``; per-node state slices
use the declared ``RunState`` keys (``NODE_STATE_KEY``). A reached node with a
missing slice surfaces an explicit unknown-shape marker (refinement rule —
never guessed in the API layer).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol

from pipeline.routing import NODE_ORDER

NODE_STATE_KEY = {
    "trend_research": "clusters",
    "contract_approval": "collection_contract",
    "listing_copy": "listing_copy",
    "design_spec": "design_spec",
    "art_render": "render_result",
    "placement": "placement",
    "aesthetic_qc": "aesthetic_qc",
    "technical_qc": "technical_qc",
    "fw_create": "fw_product",
    "publish_gate": "publish_decision",
    "shelf": "shelf_result",
}
assert set(NODE_STATE_KEY) == set(NODE_ORDER)  # tracker can never drift from the graph


class UnknownNode(ValueError):
    pass


class NodeNotReached(ValueError):
    pass


@dataclass(frozen=True)
class Snapshot:
    run_id: str
    values: dict[str, Any]
    at: Optional[str]
    interrupted: bool = False


class RunScanner(Protocol):
    def list_snapshots(self) -> list[Snapshot]: ...


class HistoryReader(Protocol):
    def history(self, run_id: str) -> list[Snapshot]: ...


class ReplayExecutor(Protocol):
    def replay(self, run_id: str, node: str, recorded: Any) -> dict[str, Any]: ...


def derive_status(values: dict[str, Any], interrupted: bool) -> str:
    """Run status from recorded state (pure)."""
    if interrupted:
        return "awaiting_approval"
    if values.get("errors"):
        return "failed"
    visited = values.get("visited") or []
    if len(visited) >= len(NODE_ORDER) and all(n in visited for n in NODE_ORDER):
        return "complete"
    return "running"


def summarize(run_id: str, values: dict[str, Any], interrupted: bool,
              started_at: Optional[str], updated_at: Optional[str]) -> dict[str, Any]:
    visited = values.get("visited") or []
    current = next((n for n in reversed(NODE_ORDER) if n in visited), None)
    return {
        "id": run_id,
        "collection_id": values.get("collection_id"),
        "design_id": values.get("design_id"),
        "status": derive_status(values, interrupted),
        "current_node": current,
        "started_at": started_at,
        "updated_at": updated_at,
    }


def node_detail(history: list[Snapshot]) -> list[dict[str, Any]]:
    """Per-node recorded state in locked order (pure).

    For each node, the LATEST snapshot whose visited list contains it (regen
    loops re-run nodes — latest wins). Unreached nodes carry null state.
    """
    latest: dict[str, Snapshot] = {}
    for snap in history:  # newest-first; first hit per node is the latest run
        for node in snap.values.get("visited") or []:
            latest.setdefault(node, snap)
    detail = []
    for node in NODE_ORDER:
        snap = latest.get(node)
        if snap is None:
            detail.append({"node": node, "reached": False, "state": None, "at": None})
            continue
        key = NODE_STATE_KEY[node]
        state = snap.values.get(key)
        if state is None:
            state = {"unknown_shape": True,
                     "note": f"{node} was reached but {key!r} is absent — pipeline state-schema gap, not guessed"}
        detail.append({"node": node, "reached": True, "state": state, "at": snap.at})
    return detail


class RunService:
    """Listing + detail + idempotent-safe replay over injected ports."""

    def __init__(self, *, scanner: RunScanner, history: HistoryReader,
                 executor: ReplayExecutor, writer) -> None:
        self._scanner = scanner
        self._history = history
        self._executor = executor
        self._writer = writer
        self._in_flight: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def list_runs(self, *, collection: Optional[str] = None,
                 status: Optional[str] = None, date: Optional[str] = None) -> list[dict[str, Any]]:
        # Newest snapshot per thread carries current values; oldest ts starts it.
        by_run: dict[str, list[Snapshot]] = {}
        for snap in self._scanner.list_snapshots():
            by_run.setdefault(snap.run_id, []).append(snap)
        rows = []
        for run_id, snaps in by_run.items():
            current = max(snaps, key=lambda s: s.at or "")
            ats = sorted(s.at for s in snaps if s.at)
            rows.append(summarize(run_id, current.values, current.interrupted,
                                  ats[0] if ats else None, ats[-1] if ats else None))
        if collection is not None:
            rows = [r for r in rows if r["collection_id"] == collection]
        if status is not None:
            rows = [r for r in rows if r["status"] == status]
        if date is not None:
            rows = [r for r in rows if (r["started_at"] or "")[:10] == date]
        return sorted(rows, key=lambda r: r["updated_at"] or "", reverse=True)

    def run_detail(self, run_id: str) -> dict[str, Any]:
        history = self._history.history(run_id)
        if not history:
            raise KeyError(f"unknown run {run_id}")
        values = history[0].values
        return {
            **summarize(run_id, values, False, None, history[0].at),
            "nodes": node_detail(history),
            "errors": values.get("errors") or [],
        }

    def replay(self, run_id: str, node: str, *, actor_user_id: str) -> dict[str, Any]:
        if node not in NODE_ORDER:
            raise UnknownNode(f"unknown node {node!r}; locked order is {NODE_ORDER!r}")
        history = self._history.history(run_id)
        if not history:
            raise KeyError(f"unknown run {run_id}")
        visited = history[0].values.get("visited") or []
        if node not in visited:
            raise NodeNotReached(f"{node!r} never executed on run {run_id!r}")
        key = (run_id, node)
        with self._lock:
            if key in self._in_flight:
                return {"run_id": run_id, "node": node, "status": "in_flight"}
            self._in_flight.add(key)
        try:
            recorded = next(
                s.values.get(NODE_STATE_KEY[node])
                for s in history
                if node in (s.values.get("visited") or [])
            )
            result = self._executor.replay(run_id, node, recorded)
        finally:
            with self._lock:
                self._in_flight.discard(key)
        self._writer.record(
            actor_user_id=actor_user_id,
            action="run.replay",
            entity_type="run",
            entity_id=run_id,
            before={"node": node},
            after={"node": node, "status": result.get("status")},
        )
        return {"run_id": run_id, "node": node, **result}


# ------------------------------------------------------------- prod ports


class CheckpointerRunPorts:
    """Prod scanner/history/executor over the LangGraph checkpointer.

    Replay config is production-shaped: OpenRouter calls bill to the project
    (loud without OPENROUTER_API_KEY), cost rows are NOT written without a
    DATABASE_URL (the state error is explicit, never silent), and FW-touching
    replays need the live Fourthwall client (PBI-027 territory) — without it
    the fw node fails loudly instead of publishing.
    """

    def __init__(self, saver_factory=None, graph_factory=None) -> None:
        from .hitl import _default_saver_factory, _saver_session  # same package reuse

        self._saver_factory = saver_factory or _default_saver_factory
        self._saver_session = _saver_session
        self._graph_factory = graph_factory

    def _graph(self, saver):
        if self._graph_factory is not None:
            return self._graph_factory(checkpointer=saver)
        from pipeline.graph import build_graph

        return build_graph(checkpointer=saver)

    def _threads(self) -> list[str]:
        with self._saver_session(self._saver_factory) as saver:
            seen: list[str] = []
            for tup in saver.list(None):
                thread_id = ((tup.config or {}).get("configurable") or {}).get("thread_id")
                if thread_id and thread_id not in seen:
                    seen.append(thread_id)
        return seen

    def list_snapshots(self) -> list[Snapshot]:
        found: list[Snapshot] = []
        with self._saver_session(self._saver_factory) as saver:
            graph = self._graph(saver)
            for thread_id in self._threads():
                snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
                interrupted = any(
                    getattr(task, "interrupts", None) for task in snapshot.tasks
                )
                checkpoint = snapshot.config.get("checkpoint", {}) if isinstance(snapshot.config, dict) else {}
                found.append(Snapshot(
                    run_id=thread_id,
                    values=dict(snapshot.values or {}),
                    at=checkpoint.get("ts"),
                    interrupted=bool(interrupted),
                ))
        return found

    def history(self, run_id: str) -> list[Snapshot]:
        with self._saver_session(self._saver_factory) as saver:
            graph = self._graph(saver)
            out = []
            for snapshot in graph.get_state_history({"configurable": {"thread_id": run_id}}):
                checkpoint = snapshot.config.get("checkpoint", {}) if isinstance(snapshot.config, dict) else {}
                out.append(Snapshot(
                    run_id=run_id,
                    values=dict(snapshot.values or {}),
                    at=checkpoint.get("ts"),
                ))
        return out

    def replay(self, run_id: str, node: str, recorded: Any) -> dict[str, Any]:
        import os

        from pipeline.llm import OpenRouterClient

        if not os.environ.get("OPENROUTER_API_KEY"):
            raise RuntimeError("replay needs OPENROUTER_API_KEY (model calls bill to the project)")
        with self._saver_session(self._saver_factory) as saver:
            graph = self._graph(saver)
            config = {"configurable": {"thread_id": run_id, "llm_client": OpenRouterClient()}}
            graph.update_state(config, {NODE_STATE_KEY[node]: recorded}, as_node=node)
            result = graph.invoke(None, config)
        visited = (result or {}).get("visited") or []
        return {"status": "complete", "visited_tail": [n for n in visited if n in NODE_ORDER]}
