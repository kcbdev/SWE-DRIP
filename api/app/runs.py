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
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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


class RunStarter(Protocol):
    def start(
        self,
        *,
        collection_id: str,
        design_id: Optional[str] = None,
        briefs: Optional[list[dict[str, Any]]] = None,
        design_type: Optional[str] = None,
    ) -> dict[str, Any]: ...


class SpendReader(Protocol):
    def month_to_date_usd(self) -> float: ...


class SpendUnavailable(RuntimeError):
    """Month-to-date spend could not be read — refuse to start rather than guess."""


def _stored_contract(collection_id: str) -> dict[str, Any]:
    """The collection's contract from the YAML store, or ``{}`` when there is none.

    Spec C3: the contract is read from the store — the single source of truth
    (NFR-1) — so a run against an existing collection uses that collection's real
    placement templates and colorways instead of drafting placeholders. A store
    failure is not fatal here: the run falls back to node 2 drafting a candidate.
    """
    try:
        from .collections_store import CollectionNotFound, get_collections_store

        record = get_collections_store().get(collection_id)
    except CollectionNotFound:
        return {}
    except Exception:  # noqa: BLE001 - store unavailable → draft path
        return {}
    contract = record.get("contract") if isinstance(record, dict) else None
    return dict(contract) if isinstance(contract, dict) else {}


def resolve_board_image(contract: Optional[dict[str, Any]]) -> Optional[str]:
    """Inline the collection's mood board as a data URI for aesthetic QC.

    The first ``mood_board`` ref resolving under the collection's asset dir
    wins; anything missing/unreadable degrades to ``None`` (the node records
    style ``unscored`` rather than failing). Never raises — a board problem
    must not take a run down.
    """
    if not isinstance(contract, dict):
        return None
    refs = contract.get("mood_board")
    if not isinstance(refs, list):
        return None
    try:
        from .inspiration import resolve_collections_root

        slug = contract.get("collection_id") or ""
        assets_dir = resolve_collections_root() / f"{slug}.assets"
        import base64

        for ref in refs:
            if not isinstance(ref, str) or not ref.strip():
                continue
            candidate = assets_dir / ref.strip()
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            try:
                base = assets_dir.resolve()
            except OSError:
                return None
            if resolved.parent != base or not resolved.is_file():
                continue
            raw = resolved.read_bytes()
            if raw[:8] == b"\x89PNG\r\n\x1a\n":
                mime = "image/png"
            elif raw[:3] == b"\xff\xd8\xff":
                mime = "image/jpeg"
            else:
                continue
            return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
    except Exception:
        pass
    return None


def validate_briefs(briefs: Optional[list[dict[str, Any]]]) -> list[str]:
    """Return the reasons a brief set cannot start a run (empty list = valid).

    Node 1 raises on a brief that is missing its locked score fields, and an
    empty brief set silently produces zero clusters — which cascades into eight
    downstream node errors on the first live run. Catching it at the API boundary
    turns that into one actionable 422 instead of a wasted run.

    Ranges come from the pipeline's own constants, never a second copy.
    """
    from pipeline.nodes.trend import MAX_ENGAGEMENT, MAX_NOVELTY, MAX_SPECIFICITY

    if not briefs:
        return [
            "at least one brief is required — node 1 clusters briefs into collection "
            "candidates, and an empty set produces no clusters"
        ]
    errors: list[str] = []
    for index, brief in enumerate(briefs):
        if not isinstance(brief, dict):
            errors.append(f"briefs[{index}] must be an object")
            continue
        label = brief.get("id") or f"briefs[{index}]"
        for field, maximum in (
            ("engagement", MAX_ENGAGEMENT),
            ("novelty", MAX_NOVELTY),
            ("specificity", MAX_SPECIFICITY),
        ):
            value = brief.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"{label}: {field} must be a number (0-{maximum})")
            elif not 0 <= value <= maximum:
                errors.append(f"{label}: {field}={value} out of locked range 0-{maximum}")
    return errors


def runs_root() -> Path:
    """Render-artifact root, shared with ``routers/designs.py:get_runs_root``.

    Both must resolve to the same directory or a run's render cannot be served.
    A test asserts the two agree.
    """
    return Path(__file__).resolve().parent.parent.parent / "runs"


class SqlSpendReader:
    """Month-to-date spend from ``model_calls``.

    Without a datastore the answer is a genuine 0 (offline). With one
    configured, a read failure raises: starting a run we cannot account for
    would defeat the budget invariant (spec C4, anti-pattern "silently starting
    a run when the budget cap is already exceeded").
    """

    def month_to_date_usd(self) -> float:
        from sqlalchemy import text

        from .config import settings
        from .db import get_engine

        if not settings.database_url:
            return 0.0
        try:
            with get_engine().connect() as conn:
                total = conn.execute(
                    text(
                        "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM model_calls "
                        "WHERE to_char(created_at, 'YYYY-MM') = :ym"
                    ),
                    {"ym": datetime.now().strftime("%Y-%m")},
                ).scalar()
        except Exception as exc:  # noqa: BLE001 - surfaced as a refusal, never a guess
            raise SpendUnavailable(str(exc)) from exc
        return float(total or 0.0)


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
            **summarize(run_id, values, history[0].interrupted, None, history[0].at),
            "nodes": node_detail(history),
            "node_config": _config_summary(values.get("node_config") or {}),
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


class LogReader(Protocol):
    def for_run(self, run_id: str, *, node: Optional[str] = None,
                level: Optional[str] = None, since: Optional[str] = None,
                limit: int = 500) -> list[dict[str, Any]]: ...


def _config_summary(node_config: dict[str, Any]) -> dict[str, Any]:
    """Trimmed per-node runtime config so a run explains itself (spec C2).

    Only the operator-meaningful fields travel — prompt text stays in the
    settings store, never in a run payload.
    """
    summary: dict[str, Any] = {}
    for node in NODE_ORDER:
        entry = node_config.get(node)
        if isinstance(entry, dict):
            summary[node] = {
                "model": entry.get("model"),
                "params": entry.get("params") or {},
                "enabled": bool(entry.get("enabled", True)),
            }
        else:
            summary[node] = {"model": None, "params": {}, "enabled": True}
    return summary


class SqlLogReader:
    """Per-run log reads over ``run_logs`` (PBI-042, spec C7).

    No ``DATABASE_URL`` → ``[]`` (offline runs keep no rows server-side, so
    empty is the honest answer). A configured-but-broken database raises —
    callers surface it, never synthesize rows.
    """

    def for_run(self, run_id: str, *, node: Optional[str] = None,
                level: Optional[str] = None, since: Optional[str] = None,
                limit: int = 500) -> list[dict[str, Any]]:
        from sqlalchemy import text

        from .config import settings
        from .db import get_engine

        if not settings.database_url:
            return []
        clauses = ["run_id = :run_id"]
        params: dict[str, Any] = {"run_id": run_id, "limit": max(1, min(limit, 1000))}
        if node is not None:
            clauses.append("node = :node")
            params["node"] = node
        if level is not None:
            clauses.append("level = :level")
            params["level"] = level
        if since is not None:
            clauses.append("created_at >= :since")
            params["since"] = since
        with get_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT node, level, message, detail_json, "
                        "to_char(created_at, 'YYYY-MM-DD\"T\"HH24:MI:SS.MSOF') AS ts "
                        "FROM run_logs WHERE " + " AND ".join(clauses) + " "
                        "ORDER BY created_at ASC LIMIT :limit"
                    ),
                    params,
                )
                .mappings()
                .all()
            )
        return [
            {"node": r["node"], "level": r["level"], "message": r["message"],
             "detail": r["detail_json"] or {}, "ts": r["ts"]}
            for r in rows
        ]


class CheckpointerRunStarter:
    """Start a pipeline run (spec C1–C5, C7).

    The run's whole record is the checkpointer thread — ``run_id`` IS the
    ``thread_id`` (NFR-1). Configuration is read from the running system at
    start time: HITL flags from the settings store (the same source the Settings
    UI writes) and render artifacts under the root ``designs.py`` serves from.

    Phase lock (C5): ``fw_live`` is never set and no Fourthwall write client is
    ever injected, so nothing here can create or publish a storefront product.
    Node 9 records an explicit error instead (PBI-027 owns that path).

    C7: the graph runs on a daemon thread, so the caller's request returns
    immediately. A failure that escapes the graph is recorded into the run's own
    state (``errors``) so it shows as ``failed`` in the Runs screen rather than
    as a zombie "running" row.
    """

    def __init__(self, saver_factory=None, graph_factory=None) -> None:
        from .hitl import _default_saver_factory, _saver_session  # same-package reuse

        self._saver_factory = saver_factory or _default_saver_factory
        self._saver_session = _saver_session
        self._graph_factory = graph_factory

    def _graph(self, saver):
        if self._graph_factory is not None:
            return self._graph_factory(checkpointer=saver)
        from pipeline.graph import build_graph

        return build_graph(checkpointer=saver)

    def start(
        self,
        *,
        collection_id: str,
        design_id: Optional[str] = None,
        briefs: Optional[list[dict[str, Any]]] = None,
        design_type: Optional[str] = None,
    ) -> dict[str, Any]:
        from pipeline.llm import OpenRouterClient
        from pipeline.node_config import resolve_all_node_configs
        from pipeline.runlog import SqlRunLogger

        from .db import get_engine
        from .settings_store import get_hitl_flags
        from .stream import broker

        run_id = uuid.uuid4().hex
        # A run needs a stable design_id for its state record and render path;
        # the run id is unique and never a fabricated business value.
        resolved_design = design_id or run_id

        # Built here, not in the thread, so a missing key is a loud, attributable
        # failure of this request instead of a silent dead thread.
        client = OpenRouterClient()
        cost_engine = get_engine()
        hitl = get_hitl_flags()        # Resolved ONCE: editing node config never changes a run in flight
        # (spec C2), and the snapshot rides in state so the run explains itself.
        node_config = {node: conf.as_dict() for node, conf in resolve_all_node_configs().items()}
        # The collection contract is read from the YAML store (spec C3) — the
        # single source of truth (NFR-1). A run against an existing collection
        # must use ITS contract (with real placement templates), not a fresh
        # placeholder draft.
        contract = _stored_contract(collection_id)

        config = {
            "configurable": {
                "thread_id": run_id,
                "hitl": hitl,
                "llm_client": client,
                "cost_engine": cost_engine,
                "node_config": node_config,
                # Per-node logs (spec C7): SQL-backed, best-effort — a logging
                # failure never breaks the run, and rows fan out as run.log
                # SSE events for live viewing.
                "run_logger": SqlRunLogger(cost_engine, run_id, publish=broker.publish),
                # Mood board for style-conformance QC (PBI-051): inlined once
                # here so resume/replay inherit it from state, below.
                "board_image": resolve_board_image(contract),
                "run_dir": str(runs_root() / resolved_design),
                # Per-design choice; `placement` reads it from config and refuses
                # to infer one (locked vocabulary).
                "design_type": design_type,
                # fw_live / fw_client deliberately absent — see phase lock (C5).
            }
        }
        state: dict[str, Any] = {
            "design_id": resolved_design,
            "collection_id": collection_id,
            "briefs": briefs or [],
            "node_config": node_config,
            # Carried for resume/replay: placement reads it from config, and
            # rebuilt configs must not infer one (same bug class as the
            # run_logger drop — found on the second MCP-driven live run).
            "design_type": design_type,
            # Frozen so a later resume/replay replays the same gates (a resumed
            # node only returns its resume value while its gate is still ON).
            "hitl": hitl,
        }
        if contract:
            state["collection_contract"] = contract
        threading.Thread(
            target=self._execute,
            args=(run_id, state, config),
            name=f"pipeline-run-{run_id}",
            daemon=True,
        ).start()
        return {
            "run_id": run_id,
            "status": "running",
            "collection_id": collection_id,
            "design_id": resolved_design,
            "hitl": hitl,
        }

    def _execute(self, run_id: str, state: dict[str, Any], config: dict[str, Any]) -> None:
        """Run the graph; on failure, record it into the run's own state."""
        try:
            with self._saver_session(self._saver_factory) as saver:
                self._graph(saver).invoke(state, config)
        except Exception as exc:  # noqa: BLE001 - must surface, never vanish
            traceback.print_exc()
            self._record_failure(run_id, config, exc)

    def _record_failure(self, run_id: str, config: dict[str, Any], exc: Exception) -> None:
        try:
            with self._saver_session(self._saver_factory) as saver:
                self._graph(saver).update_state(
                    config, {"errors": [f"run.start failed: {type(exc).__name__}: {exc}"]}
                )
        except Exception:  # noqa: BLE001 - best effort; the traceback above is the record
            print(f"run {run_id}: could not record failure into state")


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
                # `run_detail` derives status from the newest snapshot, so the
                # interrupt flag must ride along — otherwise the detail endpoint
                # reports "failed" for a run the list correctly calls
                # "awaiting_approval".
                interrupted = any(
                    getattr(task, "interrupts", None) for task in (snapshot.tasks or [])
                )
                out.append(Snapshot(
                    run_id=run_id,
                    values=dict(snapshot.values or {}),
                    at=checkpoint.get("ts"),
                    interrupted=bool(interrupted),
                ))
        return out

    def replay(self, run_id: str, node: str, recorded: Any) -> dict[str, Any]:
        """Re-run the graph from ``node`` on its recorded upstream state.

        Rebuilds the same runtime config the start path supplied — a replay
        executes every node after ``node``, so it needs `llm_client`,
        `cost_engine`, the frozen HITL flags, the frozen `node_config` snapshot
        and the render root, not just a thread id.
        """
        import os

        from pipeline.llm import OpenRouterClient
        from pipeline.runlog import SqlRunLogger

        from .db import get_engine
        if not os.environ.get("OPENROUTER_API_KEY"):
            raise RuntimeError("replay needs OPENROUTER_API_KEY (model calls bill to the project)")
        with self._saver_session(self._saver_factory) as saver:
            graph = self._graph(saver)
            state = dict(graph.get_state({"configurable": {"thread_id": run_id}}).values or {})
            engine = get_engine()
            config = {
                "configurable": {
                    "thread_id": run_id,
                    "llm_client": OpenRouterClient(),
                    "cost_engine": engine,
                    "run_logger": SqlRunLogger(engine, run_id),
                    "board_image": resolve_board_image(state.get("collection_contract") or {}),
                    "hitl": state.get("hitl") or {},
                    "node_config": state.get("node_config") or {},
                    "design_type": state.get("design_type"),
                    "run_dir": str(runs_root() / str(state.get("design_id") or run_id)),
                }
            }
            graph.update_state(config, {NODE_STATE_KEY[node]: recorded}, as_node=node)
            result = graph.invoke(None, config)
        visited = (result or {}).get("visited") or []
        return {"status": "complete", "visited_tail": [n for n in visited if n in NODE_ORDER]}
