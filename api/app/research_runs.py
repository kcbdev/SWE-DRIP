"""Research-run trigger + inspection over the checkpointer (PBI-055, spec C4/C6).

The PBI-050 collection graph runs here the way item runs run in
``runs.py``: ``run_id`` IS the checkpointer ``thread_id`` (NFR-1 — no
parallel run store), namespaced with ``RESEARCH_RUN_PREFIX`` so the item
surface (``/api/runs``) and this surface stay disjoint on the shared
checkpointer. Research threads never write ``active``; drafts enter the
PBI-020 lifecycle through the existing approve endpoint.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Optional

from pipeline.collection_graph import (
    RESEARCH_DEFAULT_HITL,
    RESEARCH_ORDER,
    RESEARCH_RUN_PREFIX,
    build_collection_graph,
)
from pipeline.lineage import build_research_inputs

from .runs import CheckpointerRunPorts, Snapshot

# Display stage per most-recently-visited node (the card's vocabulary).
RESEARCH_STAGE = {
    "inspiration_review": "started",
    "style_synthesis": "synthesizing",
    "mood_board": "board_rendering",
    "contract_draft": "drafting",
    "collection_gate": "awaiting_approval",
}

# State slice per node for the detail view (mirrors NODE_STATE_KEY).
RESEARCH_STATE_KEY = {
    "inspiration_review": "inspiration",
    "style_synthesis": "synthesis",
    "mood_board": "board",
    "contract_draft": "draft_contract",
    "collection_gate": "gate_decision",
}
assert set(RESEARCH_STATE_KEY) == set(RESEARCH_ORDER)


def is_research_run(run_id: str) -> bool:
    """Namespace check shared with the item surface (runs.py guards)."""
    return isinstance(run_id, str) and run_id.startswith(RESEARCH_RUN_PREFIX)


# Contract keys owned by the collections lifecycle (PBI-020), never by the
# research handoff: the store PATCH path rejects status transitions, and
# created/stamp history belongs to the candidate, not the run.
LIFECYCLE_OWNED = ("status", "approved_at", "retired_at", "survivor_products",
                   "created_by", "created_at")


def build_handoff_contract(values: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Draft to persist after an approved research gate (pure).

    Prefers the CEO-edited contract, else the assembled draft. Forces draft
    status + identity (the handoff never activates), and backfills the board
    ref when the draft predates board linkage (pre-PBI-059 runs). Returns
    None unless the gate approved with a usable draft.
    """
    from pipeline.nodes.research_draft import board_display_ref

    decision = values.get("gate_decision") or {}
    if not decision.get("approved"):
        return None
    draft = dict(decision.get("edited_contract") or values.get("draft_contract") or {})
    if not draft.get("collection_id"):
        return None
    draft["collection_id"] = str(draft["collection_id"])
    draft["status"] = "draft"
    if not draft.get("mood_board"):
        ref = board_display_ref((values.get("board") or {}).get("file_ref"))
        if ref:
            draft["mood_board"] = [ref]
    return draft


def persist_handoff(store, contract: dict[str, Any]) -> dict[str, Any]:
    """Create-or-update the candidate from an approved draft (PBI-059).

    Update path excludes lifecycle-owned keys (the store rejects status
    transitions); create path writes the full draft (always status draft).
    Returns ``{"record", "before", "created"}`` for the audit row.
    """
    from .collections_store import CollectionNotFound

    slug = contract["collection_id"]
    try:
        before = store.get(slug)["contract"]
    except CollectionNotFound:
        before = None
    if before is None:
        record = store.create(contract)
        return {"record": record, "before": None, "created": True}
    patch = {k: v for k, v in contract.items()
             if k not in ("collection_id", *LIFECYCLE_OWNED)}
    record = store.update(slug, patch)
    return {"record": record, "before": before, "created": False}


def derive_research_status(values: dict[str, Any], interrupted: bool) -> str:
    """Status from recorded research state (pure)."""
    if interrupted:
        return "awaiting_approval"
    if values.get("errors"):
        return "failed"
    visited = values.get("visited") or []
    if visited and all(n in visited for n in RESEARCH_ORDER):
        return "complete"
    if not visited:
        return "started"
    return RESEARCH_STAGE.get(visited[-1], "started")


def research_node_detail(history: list[Snapshot]) -> list[dict[str, Any]]:
    """Per-node recorded state in locked research order (pure)."""
    latest: dict[str, Snapshot] = {}
    for snap in history:  # newest-first; first hit per node wins
        for node in snap.values.get("visited") or []:
            latest.setdefault(node, snap)
    detail = []
    for node in RESEARCH_ORDER:
        snap = latest.get(node)
        if snap is None:
            detail.append({"node": node, "reached": False, "state": None, "at": None})
            continue
        key = RESEARCH_STATE_KEY[node]
        state = snap.values.get(key)
        if state is None:
            state = {"unknown_shape": True,
                     "note": f"{node} was reached but {key!r} is absent — state-schema gap, not guessed"}
        detail.append({"node": node, "reached": True, "state": state, "at": snap.at})
    return detail


def summarize_research(run_id: str, values: dict[str, Any], interrupted: bool,
                       started_at: Optional[str], updated_at: Optional[str]) -> dict[str, Any]:
    """List-row shape for one research run (pure)."""
    board = values.get("board") or {}
    visited = values.get("visited") or []
    return {
        "id": run_id,
        "collection_slug": values.get("collection_slug"),
        "status": derive_research_status(values, interrupted),
        "current_stage": RESEARCH_STAGE.get(visited[-1], "started") if visited else "started",
        "board_version": board.get("board_version"),
        "diversity_flags": values.get("diversity_flags") or [],
        "started_at": started_at,
        "updated_at": updated_at,
    }


def research_detail(run_id: str, values: dict[str, Any], interrupted: bool,
                    at: Optional[str], history: list[Snapshot]) -> dict[str, Any]:
    """Full detail shape for one research run (pure)."""
    board = values.get("board") or {}
    return {
        **summarize_research(run_id, values, interrupted, None, at),
        "board": board or None,
        "draft_contract": values.get("draft_contract"),
        "gate_decision": values.get("gate_decision"),
        "nodes": research_node_detail(history),
        "errors": values.get("errors") or [],
    }


def build_research_state(store, inspiration_store, slug: str) -> dict[str, Any]:
    """Seed state for a research run from the YAML store (pure IO assembly).

    Raises CollectionNotFound (unknown slug) and ValueError (nothing curated
    — the review node would fail loudly anyway, but the trigger refuses
    earlier with an actionable message).
    """
    record = store.get(slug)  # raises CollectionNotFound
    contract = record["contract"]
    listing = inspiration_store.list(slug)
    assets = listing.get("assets") or []
    refs = listing.get("refs") or []
    if not assets and not refs:
        raise ValueError(
            f"no inspiration curated for {slug!r} — upload an asset or link a ref first")
    contracts = [r["contract"] for r in store.list()]
    inputs = build_research_inputs(contracts)
    return {
        "collection_slug": slug,
        "collection_theme": contract.get("theme") or slug,
        "style_archetype": contract.get("style_archetype") or "",
        "inspiration": {"assets": assets, "refs": refs},
        "avoid": inputs["avoid"],
        "lineage": inputs["lineage"],
    }


class ResearchRunStarter:
    """Start a collection-research run (spec C4).

    Mirrors ``CheckpointerRunStarter``: run_id IS thread_id, the graph runs
    on a daemon thread, an escaping failure is recorded into the run's own
    state. Research threads never write ``active`` (graph invariant) and
    carry no Fourthwall client. Factories are injectable so the whole
    trigger → gate → resume path runs offline in tests.
    """

    def __init__(self, saver_factory=None, graph_factory=None, llm_factory=None,
                 engine_factory=None, logger_factory=None, store_factory=None,
                 inspiration_factory=None) -> None:
        from .hitl import _default_saver_factory, _saver_session  # same-package reuse

        self._saver_factory = saver_factory or _default_saver_factory
        self._saver_session = _saver_session
        self._graph_factory = graph_factory
        self._llm_factory = llm_factory
        self._engine_factory = engine_factory
        self._logger_factory = logger_factory
        self._store_factory = store_factory
        self._inspiration_factory = inspiration_factory

    def _graph(self, saver):
        if self._graph_factory is not None:
            return self._graph_factory(checkpointer=saver)
        return build_collection_graph(checkpointer=saver)

    def start(self, *, collection_slug: str, actor_user_id: str = "") -> dict[str, Any]:
        from pipeline.paths import collections_root

        from .collections_store import get_collections_store
        from .inspiration import InspirationStore

        store = self._store_factory() if self._store_factory else get_collections_store()
        inspiration = (self._inspiration_factory()
                       if self._inspiration_factory else InspirationStore())
        state = build_research_state(store, inspiration, collection_slug)

        run_id = RESEARCH_RUN_PREFIX + uuid.uuid4().hex
        llm_client = self._llm_factory() if self._llm_factory else _prod_llm_client()
        cost_engine = self._engine_factory() if self._engine_factory else _prod_engine()
        if self._logger_factory:
            run_logger = self._logger_factory(cost_engine, run_id)
        else:
            from pipeline.runlog import SqlRunLogger

            from .stream import broker

            run_logger = SqlRunLogger(cost_engine, run_id, publish=broker.publish)
        hitl = dict(RESEARCH_DEFAULT_HITL)  # frozen: gates stay as started
        config = {
            "configurable": {
                "thread_id": run_id,
                "hitl": hitl,
                "llm_client": llm_client,
                "cost_engine": cost_engine,
                "run_logger": run_logger,
                # Durable asset root (PBI-053): explicit so the board lands on
                # the volume in production, not on a CWD-relative default.
                "research_assets_dir": str(
                    collections_root() / f"{collection_slug}.assets"),
            }
        }
        state["hitl"] = hitl
        _ = actor_user_id  # audited by the router, not the starter
        threading.Thread(
            target=self._execute,
            args=(run_id, state, config),
            name=f"research-run-{run_id}",
            daemon=True,
        ).start()
        return {"run_id": run_id, "status": "started", "collection_slug": collection_slug}

    def _execute(self, run_id: str, state: dict[str, Any], config: dict[str, Any]) -> None:
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
                    config, {"errors": [f"research.start failed: {type(exc).__name__}: {exc}"]}
                )
        except Exception:  # noqa: BLE001 - best effort; the traceback above is the record
            print(f"research run {run_id}: could not record failure into state")


def _prod_llm_client():
    from pipeline.llm import OpenRouterClient

    return OpenRouterClient()


def _prod_engine():
    from .db import get_engine

    return get_engine()


class ResearchRunPorts(CheckpointerRunPorts):
    """Scanner/history over the shared checkpointer, research namespace only."""

    def __init__(self, saver_factory=None) -> None:
        super().__init__(saver_factory=saver_factory, graph_factory=build_collection_graph)

    def list_research_snapshots(self) -> list[Snapshot]:
        return [s for s in self.list_snapshots() if is_research_run(s.run_id)]

    def history(self, run_id: str) -> list[Snapshot]:
        if not is_research_run(run_id):
            return []  # disjoint surfaces: item threads are unknown here
        return super().history(run_id)


def list_research_runs(ports: ResearchRunPorts) -> list[dict[str, Any]]:
    """Newest-state rows for research threads only (pure assembly)."""
    by_run: dict[str, list[Snapshot]] = {}
    for snap in ports.list_research_snapshots():
        by_run.setdefault(snap.run_id, []).append(snap)
    rows = []
    for run_id, snaps in by_run.items():
        current = max(snaps, key=lambda s: s.at or "")
        ats = sorted(s.at for s in snaps if s.at)
        rows.append(summarize_research(run_id, current.values, current.interrupted,
                                       ats[0] if ats else None, ats[-1] if ats else None))
    return sorted(rows, key=lambda r: r["updated_at"] or "", reverse=True)


def research_run_detail(ports: ResearchRunPorts, run_id: str) -> dict[str, Any]:
    """Full detail or KeyError (unknown run)."""
    history = ports.history(run_id)
    if not history:
        raise KeyError(f"unknown research run {run_id}")
    values = history[0].values
    return research_detail(run_id, values, history[0].interrupted, history[0].at, history)


class ResearchGraphRunner:
    """State reads + resume against the research graph (never the item graph)."""

    def __init__(self, saver_factory=None, llm_factory=None,
                 engine_factory=None, logger_factory=None) -> None:
        from .hitl import _default_saver_factory, _saver_session

        self._saver_factory = saver_factory or _default_saver_factory
        self._saver_session = _saver_session
        self._llm_factory = llm_factory
        self._engine_factory = engine_factory
        self._logger_factory = logger_factory

    def _graph(self, saver):
        return build_collection_graph(checkpointer=saver)

    def get_state_values(self, thread_id: str) -> dict[str, Any]:
        with self._saver_session(self._saver_factory) as saver:
            snapshot = self._graph(saver).get_state({"configurable": {"thread_id": thread_id}})
        return dict(snapshot.values or {})

    def resume(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Resume a paused research gate, rebuilding the runtime start supplied.

        Only the gate node re-executes before END, but the config must still
        carry the LLM client, cost engine, logger, frozen HITL flags, and the
        asset dir — a bare thread_id resume fails the same way item runs did
        before PBI-037's fix (no llm_client in config).
        """
        from langgraph.types import Command

        from pipeline.paths import collections_root

        with self._saver_session(self._saver_factory) as saver:
            graph = self._graph(saver)
            state = dict(graph.get_state({"configurable": {"thread_id": thread_id}}).values or {})
            slug = str(state.get("collection_slug") or "")
            hitl = state.get("hitl") or dict(RESEARCH_DEFAULT_HITL)
            engine = self._engine_factory() if self._engine_factory else _prod_engine()
            llm_client = self._llm_factory() if self._llm_factory else _prod_llm_client()
            if self._logger_factory:
                logger = self._logger_factory(engine, thread_id)
            else:
                logger = _prod_run_logger(engine, thread_id)
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "hitl": hitl,
                    "llm_client": llm_client,
                    "cost_engine": engine,
                    "run_logger": logger,
                    "research_assets_dir": str(
                        collections_root() / f"{slug}.assets") if slug else "",
                }
            }
            graph.invoke(Command(resume=payload), config)
        return {"thread_id": thread_id, "resumed": True}


def _prod_run_logger(engine, run_id):
    from pipeline.runlog import SqlRunLogger

    from .stream import broker

    return SqlRunLogger(engine, run_id, publish=broker.publish)


def serve_board_file(slug: str, ref: str, collections_root_path: Optional[Path] = None) -> tuple[bytes, str]:
    """Same-origin board bytes for a mood-board ref (pure IO helper).

    Boards render into the collection's asset dir before any contract names
    them, so serving is scoped to the dir (not to the contract's ref list):
    relative-ref validation + traversal guard + image-suffix gate. Raises
    CollectionNotFound (unknown collection/asset) and ValueError (bad ref).
    """
    from pipeline.paths import collections_root

    from .collections_schema import _relative_artifact_refs
    from .collections_store import CollectionNotFound

    try:
        _relative_artifact_refs([ref], "mood_board")
    except ValueError as exc:
        raise ValueError(str(exc)) from None
    root = Path(collections_root_path) if collections_root_path else collections_root()
    try:
        base = (root / f"{slug}.assets").resolve()
    except OSError:
        raise CollectionNotFound(f"unknown collection {slug!r}") from None
    try:
        path = (base / ref).resolve()
    except OSError:
        raise CollectionNotFound(f"unknown board ref {ref!r}") from None
    try:
        is_inside = path.is_relative_to(base)
    except (OSError, ValueError):
        is_inside = False
    if not is_inside or not path.is_file():
        raise CollectionNotFound(f"unknown board ref {ref!r}")
    suffix = path.suffix.lower()
    if suffix == ".png":
        media_type = "image/png"
    elif suffix in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    else:
        raise CollectionNotFound(f"unknown board ref {ref!r}")
    return path.read_bytes(), media_type
