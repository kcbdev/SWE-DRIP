"""HITL resume service (spec C1/C2/C4/C6).

One aggregated queue, no second approval model: open gates are gathered from
the LangGraph checkpointer's live interrupt state and merged with thin
``hitl_approvals`` index rows (query/filter only — the interrupt is the source
of truth, NFR-1). Decisions map to exactly one ``Command(resume=...)`` per
decision (idempotent: replays return the recorded decision, never re-resume),
and every decision writes an audit row through the shared writer.

Resume-payload mapping per node (refinement rule: shapes match the interrupt
payloads pipeline-core defines; mismatches are pipeline-core bugs, raised as
``HitlUnknownNode`` — never silently patched here):
- contract_approval: approve selects via ``selection.approved_cluster_id``,
  or the single open cluster when unambiguous; reject/regenerate resume a
  null selection (node error path — the run degrades safely, never publishes).
- publish_gate: approve → ``{"approved": True}``; reject/regenerate →
  ``{"approved": False}`` (product stays DRAFT either way in this phase).
- aesthetic_qc (human-review interrupt): the decision is recorded
  authoritatively; resume continues the run (PBI-013 semantics).

Crash-window honesty: claim → resume → audit. If resume FAILS, the claim is
rolled back to pending and the error propagates, so a retry can still resume
exactly once. If resume SUCCEEDS but the audit write fails, the claim is KEPT
(reopening would let a retry resume an already-consumed gate — worse); the
error propagates and the decided-but-unaudited row stays visible in the index.
A hard process crash between claim-commit and resume leaves a decided row
with a live interrupt; re-listing the queue surfaces a FRESH pending row for
that gate (the stale decided row is retained as history), so the decision can
still be made. Concurrent double-submits collapse on the atomic claim
(``UPDATE ... WHERE status='pending'``).

Known limitation (owned by a pipeline-core follow-up, NOT patched here):
an aesthetic_qc REJECT is recorded authoritatively (index + audit) but the
node discards the resume value and the run continues to technical QC — the
default-on publish gate remains the backstop and no auto-publish path exists.
Reject/stop run-control semantics need node-side handling; changing gates is
out of scope for this service (hitl-approvals spec).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator, Optional, Protocol

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .audit import AuditWriter, get_audit_writer
from .db import get_engine
from .models import hitl_approvals

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
REGENERATE_REQUESTED = "regenerate_requested"

ACTION_TO_STATUS = {"approve": APPROVED, "reject": REJECTED, "regenerate": REGENERATE_REQUESTED}
STATUS_TO_ACTION = {status: action for action, status in ACTION_TO_STATUS.items()}
ACTIONS = tuple(ACTION_TO_STATUS)


class HitlStale(RuntimeError):
    """Run state unavailable (thread gone/retained) — caller maps to 409."""


class HitlUnknownNode(RuntimeError):
    """No resume mapping for this node — a pipeline-core bug. Maps to 422."""


class HitlAmbiguous(RuntimeError):
    """Decision needs disambiguation (e.g. which cluster). Maps to 422."""


@dataclass(frozen=True)
class InterruptInfo:
    run_id: str
    node: str
    payload: dict[str, Any]
    interrupt_id: str
    waiting_since: Optional[str] = None


class CheckpointGateSource(Protocol):
    def list_interrupts(self) -> list[InterruptInfo]: ...


class GraphRunner(Protocol):
    def get_state_values(self, thread_id: str) -> dict[str, Any]: ...
    def resume(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class ApprovalIndex(Protocol):
    def list_open(self) -> list[dict[str, Any]]: ...
    def list_for_run(self, run_id: str) -> list[dict[str, Any]]: ...
    def distinct_run_ids(self, limit: int = 50) -> list[str]: ...
    def get(self, item_id: int) -> Optional[dict[str, Any]]: ...
    def ensure_pending(self, run_id: str, node: str) -> dict[str, Any]: ...
    def claim(
        self, item_id: int, *, status: str, reviewer_user_id: str, note: Optional[str]
    ) -> Optional[dict[str, Any]]: ...
    def reopen(self, item_id: int) -> None: ...


def entity_ref(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Entity reference for a gate payload (pure)."""
    if node == "contract_approval":
        contracts = payload.get("contracts") or [{}]
        first = contracts[0] if isinstance(contracts[0], dict) else {}
        return {
            "type": "collection_contract",
            "id": first.get("collection_id"),
            "label": first.get("theme") or node,
        }
    if node == "publish_gate":
        product = payload.get("product") or {}
        return {"type": "product", "id": product.get("id"), "label": product.get("title") or node}
    if node == "aesthetic_qc":
        failing = payload.get("failing") or []
        return {"type": "design_qc", "id": None, "label": f"failing: {', '.join(failing) or '?'}", "attempts": payload.get("attempts")}
    return {"type": node, "id": None, "label": node}


def build_resume_payload(
    node: str,
    action: str,
    *,
    clusters: list[dict[str, Any]] | None = None,
    selection: dict[str, Any] | None = None,
    note: Optional[str] = None,
) -> dict[str, Any]:
    """Map (node, action) to the node's resume payload (pure)."""
    if node == "contract_approval":
        if action == "approve":
            ids = [c.get("cluster_id") for c in (clusters or []) if c.get("cluster_id")]
            chosen = (selection or {}).get("approved_cluster_id")
            if chosen:
                if chosen not in ids:
                    raise HitlAmbiguous(f"unknown approved_cluster_id {chosen!r}; open: {ids!r}")
                return {"approved_cluster_id": chosen}
            if len(ids) == 1:
                return {"approved_cluster_id": ids[0]}
            raise HitlAmbiguous(f"approve needs selection.approved_cluster_id; open: {ids!r}")
        return {"approved_cluster_id": None}
    if node == "publish_gate":
        payload: dict[str, Any] = {"approved": action == "approve"}
        if note:
            payload["note"] = note
        return payload
    if node == "aesthetic_qc":
        payload = {"decision": action}
        if note:
            payload["note"] = note
        return payload
    raise HitlUnknownNode(f"no resume mapping for node {node!r}")


@contextmanager
def _saver_session(factory) -> Iterator[Any]:
    """Enter saver factories that are context managers (sync PostgresSaver)."""
    saver = factory()
    if hasattr(saver, "__enter__"):
        with saver as opened:
            yield opened
    else:
        yield saver


def _default_saver_factory():
    """Offline-safe saver: MemorySaver unless DATABASE_URL is set (sync PG)."""
    import os

    url = os.environ.get("DATABASE_URL")
    if not url:
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    from langgraph.checkpoint.postgres import PostgresSaver

    return PostgresSaver.from_conn_string(url)


def _serialize(row: Any) -> dict[str, Any]:
    data = dict(row)
    decided = data.get("decided_at")
    if isinstance(decided, datetime):
        data["decided_at"] = decided.isoformat()
    return data


class CheckpointerGateSource:
    """Prod gate source: live interrupts scanned from the checkpointer.

    v1 scans threads newest-first via ``saver.list(None)`` and reads each
    thread's task interrupts through a compiled graph. No run state is
    mirrored anywhere — payloads are read transiently for the merge. At our
    scale (tens of runs) the scan is trivial; a busier future wants a
    checkpoint-listener instead of a scan (recorded, not built).
    """

    def __init__(self, saver_factory=None, graph_factory=None) -> None:
        self._saver_factory = saver_factory or _default_saver_factory
        self._graph_factory = graph_factory

    def list_interrupts(self) -> list[InterruptInfo]:
        from pipeline.graph import build_graph

        found: list[InterruptInfo] = []
        # Phase 1 — collect thread ids (and their checkpoint timestamp) with the
        # list cursor FULLY CONSUMED, then let the session close. Reading graph
        # state while `saver.list()` is still open deadlocks against the saver's
        # connection pool: the queue hung for 25s+ and timed out in production.
        # `CheckpointerRunPorts` already splits these two steps (see `_threads()`
        # vs `list_snapshots`), which is why `/api/runs` stayed fast while
        # `/api/approvals` did not.
        with _saver_session(self._saver_factory) as saver:
            threads: list[tuple[str, Optional[str]]] = []
            seen: set[str] = set()
            for tup in saver.list(None):
                thread_id = ((tup.config or {}).get("configurable") or {}).get("thread_id")
                if not thread_id or thread_id in seen:
                    continue
                seen.add(thread_id)
                checkpoint = tup.checkpoint or {}
                threads.append((thread_id, checkpoint.get("ts")))

        # Phase 2 — fresh session: safe to issue queries now.
        with _saver_session(self._saver_factory) as saver:
            graph = (self._graph_factory or build_graph)(checkpointer=saver)
            for thread_id, waiting_since in threads:
                snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
                for task in snapshot.tasks or []:
                    for intr in task.interrupts or []:
                        found.append(
                            InterruptInfo(
                                run_id=thread_id,
                                node=task.name,
                                payload=dict(intr.value) if isinstance(intr.value, dict) else {"value": intr.value},
                                interrupt_id=intr.id,
                                waiting_since=waiting_since,
                            )
                        )
        return found


class SyncGraphRunner:
    """Prod runner: sync resume against the sync saver (no asyncio in the API)."""

    def __init__(self, saver_factory=None) -> None:
        self._saver_factory = saver_factory or _default_saver_factory

    def _graph(self, saver):
        from pipeline.graph import build_graph

        return build_graph(checkpointer=saver)

    def get_state_values(self, thread_id: str) -> dict[str, Any]:
        with _saver_session(self._saver_factory) as saver:
            snapshot = self._graph(saver).get_state({"configurable": {"thread_id": thread_id}})
        return dict(snapshot.values or {})

    def resume(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from langgraph.types import Command

        with _saver_session(self._saver_factory) as saver:
            self._graph(saver).invoke(
                Command(resume=payload), {"configurable": {"thread_id": thread_id}}
            )
        return {"thread_id": thread_id, "resumed": True}


class SqlApprovalIndex:
    def __init__(self, engine_factory=None) -> None:
        self._engines = engine_factory or get_engine

    def list_open(self) -> list[dict[str, Any]]:
        with self._engines().connect() as conn:
            rows = (
                conn.execute(
                    select(hitl_approvals)
                    .where(hitl_approvals.c.status == PENDING)
                    .order_by(hitl_approvals.c.id)
                )
                .mappings()
                .all()
            )
        return [_serialize(row) for row in rows]

    def get(self, item_id: int) -> Optional[dict[str, Any]]:
        with self._engines().connect() as conn:
            row = (
                conn.execute(select(hitl_approvals).where(hitl_approvals.c.id == item_id))
                .mappings()
                .first()
            )
        return _serialize(row) if row else None

    def list_for_run(self, run_id: str) -> list[dict[str, Any]]:
        """All index rows (pending + decided) for one run — calibration joins."""
        with self._engines().connect() as conn:
            rows = (
                conn.execute(
                    select(hitl_approvals)
                    .where(hitl_approvals.c.run_id == run_id)
                    .order_by(hitl_approvals.c.id)
                )
                .mappings()
                .all()
            )
        return [_serialize(row) for row in rows]

    def distinct_run_ids(self, limit: int = 50) -> list[str]:
        """Newest-first run ids known to the index (pending + decided)."""
        from sqlalchemy import desc

        with self._engines().connect() as conn:
            rows = (
                conn.execute(
                    select(hitl_approvals.c.run_id)
                    .group_by(hitl_approvals.c.run_id)
                    .order_by(desc(func.max(hitl_approvals.c.id)))
                    .limit(limit)
                )
                .scalars()
                .all()
            )
        return list(rows)

    def ensure_pending(self, run_id: str, node: str) -> dict[str, Any]:
        try:
            with self._engines().begin() as conn:
                conn.execute(
                    hitl_approvals.insert().values(run_id=run_id, node=node, status=PENDING)
                )
        except IntegrityError:
            pass  # concurrent ensure collapsed into the existing open row
        with self._engines().connect() as conn:
            row = (
                conn.execute(
                    select(hitl_approvals)
                    .where(hitl_approvals.c.run_id == run_id)
                    .where(hitl_approvals.c.node == node)
                    .where(hitl_approvals.c.status == PENDING)
                    .order_by(hitl_approvals.c.id)
                )
                .mappings()
                .first()
            )
        assert row is not None  # we just inserted it (or it already existed)
        return _serialize(row)

    def claim(
        self, item_id: int, *, status: str, reviewer_user_id: str, note: Optional[str]
    ) -> Optional[dict[str, Any]]:
        """Atomic pending→decided transition; None when already decided."""
        with self._engines().begin() as conn:
            row = (
                conn.execute(
                    hitl_approvals.update()
                    .where(hitl_approvals.c.id == item_id)
                    .where(hitl_approvals.c.status == PENDING)
                    .values(status=status, reviewer_user_id=reviewer_user_id, note=note, decided_at=func.now())
                    .returning(hitl_approvals)
                )
                .mappings()
                .first()
            )
        return _serialize(row) if row else None

    def reopen(self, item_id: int) -> None:
        """Roll a claim back to pending (resume/audit failure recovery)."""
        with self._engines().begin() as conn:
            conn.execute(
                hitl_approvals.update()
                .where(hitl_approvals.c.id == item_id)
                .where(hitl_approvals.c.status != PENDING)
                .values(status=PENDING, reviewer_user_id=None, note=None, decided_at=None)
            )


class HitlService:
    """Queue aggregation + exactly-once decision dispatch over injected ports."""

    def __init__(
        self,
        *,
        gates: CheckpointGateSource,
        index: ApprovalIndex,
        runner: GraphRunner,
        writer: AuditWriter,
    ) -> None:
        self._gates = gates
        self._index = index
        self._runner = runner
        self._writer = writer

    def list_queue(self) -> list[dict[str, Any]]:
        items = []
        for info in self._gates.list_interrupts():
            # Index maintenance on read (idempotent upsert — the interrupt,
            # not this row, is the source of truth).
            row = self._index.ensure_pending(info.run_id, info.node)
            clusters: list[dict[str, Any]] = []
            if info.node == "contract_approval":
                # Selection options for the queue UI (PBI-018): cluster_id +
                # theme straight from run state. Degrades to [] rather than
                # 500ing the whole queue on one unreadable run.
                try:
                    clusters = self._runner.get_state_values(info.run_id).get("clusters") or []
                except Exception:
                    clusters = []
            items.append(
                {
                    **row,
                    "payload": info.payload,
                    "entity_ref": entity_ref(info.node, info.payload),
                    "waiting_since": info.waiting_since,
                    "clusters": clusters,
                }
            )
        return items

    def decide(
        self,
        item_id: int,
        *,
        action: str,
        note: Optional[str],
        selection: Optional[dict[str, Any]],
        actor_user_id: str,
    ) -> dict[str, Any]:
        if action not in ACTION_TO_STATUS:
            raise ValueError(f"action must be one of {ACTIONS!r}")
        row = self._index.get(item_id)
        if row is None:
            raise KeyError(f"unknown approval {item_id}")
        if row["status"] != PENDING:
            return self._decision_view(row, resumed=False)  # idempotent replay
        live = {(i.run_id, i.node) for i in self._gates.list_interrupts()}
        if (row["run_id"], row["node"]) not in live:
            # Gate already consumed/retained away: refuse to resume a stale
            # payload into whatever the run is doing now.
            raise HitlStale(f"gate {row['node']!r} on run {row['run_id']!r} is no longer open")
        values = self._runner.get_state_values(row["run_id"])
        if not values:
            raise HitlStale(f"run state unavailable for {row['run_id']!r}")
        payload = build_resume_payload(
            row["node"],
            action,
            clusters=values.get("clusters") or [],
            selection=selection,
            note=note,
        )
        claimed = self._index.claim(
            item_id,
            status=ACTION_TO_STATUS[action],
            reviewer_user_id=actor_user_id,
            note=note,
        )
        if claimed is None:  # lost the race — return the recorded decision
            current = self._index.get(item_id)
            assert current is not None
            return self._decision_view(current, resumed=False)
        resumed_ok = False
        try:
            self._runner.resume(row["run_id"], payload)
            resumed_ok = True
            self._writer.record(
                actor_user_id=actor_user_id,
                action=f"approval.{action}",
                entity_type="approval",
                entity_id=str(item_id),
                before={"status": PENDING},
                after={"status": claimed["status"], "note": note},
            )
            _publish_decision_events(
                item_id, run_id=row["run_id"], node=row["node"], status=claimed["status"]
            )
        except Exception:
            if not resumed_ok:
                # Resume never took effect: roll back so a retry resumes once.
                # If resume SUCCEEDED and only the audit failed, the claim is
                # KEPT — reopening would let a retry double-resume a consumed
                # gate (worse than a decided-but-unaudited row).
                self._index.reopen(item_id)
            raise
        return self._decision_view(claimed, resumed=True)

    @staticmethod
    def _decision_view(row: dict[str, Any], *, resumed: bool) -> dict[str, Any]:
        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "node": row["node"],
            "action": STATUS_TO_ACTION.get(row["status"]),
            "status": row["status"],
            "reviewer_user_id": row.get("reviewer_user_id"),
            "note": row.get("note"),
            "decided_at": row.get("decided_at"),
            "resumed": resumed,
        }


def _publish_decision_events(item_id: int, *, run_id: str, node: str, status: str) -> None:
    """Best-effort SSE fan-out for a recorded decision (never breaks decide)."""
    try:
        from .stream import broker

        broker.publish_queue_delta(item_id, run_id, node, status)
        broker.publish_run_status(run_id, "resumed")
    except Exception:
        pass  # the decision is authoritative; a missed event is just a missed push


def get_gate_source() -> CheckpointGateSource:
    return CheckpointerGateSource()


def get_approval_index() -> ApprovalIndex:
    return SqlApprovalIndex()


def get_graph_runner() -> GraphRunner:
    return SyncGraphRunner()


def get_hitl_service(
    gates: CheckpointGateSource = Depends(get_gate_source),
    index: ApprovalIndex = Depends(get_approval_index),
    runner: GraphRunner = Depends(get_graph_runner),
    writer: AuditWriter = Depends(get_audit_writer),
) -> HitlService:
    return HitlService(gates=gates, index=index, runner=runner, writer=writer)
