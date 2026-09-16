"""MCP read tools (operator-mcp C2) — the REST twins, second doorway.

Every tool calls the same router endpoint function the HTTP route calls, with
a scope-checked synthesized actor: shapes are identical by construction, not
by parallel implementation. ``HTTPException`` from the router layer is
re-mapped to :class:`ToolError` preserving status meaning and wording.

Port factories (``_run_service``, ``_log_reader``, …) resolve production
ports at call time; tests monkeypatch these module attributes with fakes.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from ..audit import AuditFilters
from ..runs import CheckpointerRunPorts, LogReader, RunService
from .auth import SCOPE_READ, ToolError, require_scope, tool_actor


class _NullWriter:
    def record(self, **kwargs: Any) -> None:
        pass


def _run_service() -> RunService:
    from ..routers import runs as runs_router

    ports = CheckpointerRunPorts()
    return runs_router.get_run_service(writer=_NullWriter(), ports=ports)  # type: ignore[arg-type]


def _log_reader() -> LogReader:
    from ..routers import runs as runs_router

    return runs_router.get_log_reader()


def _hitl_service() -> Any:
    from ..hitl import get_hitl_service

    return get_hitl_service()


def _audit_reader() -> Any:
    from ..routers import audit as audit_router

    return audit_router.get_audit_reader()


def _graph_runner() -> Any:
    from ..hitl import get_graph_runner

    return get_graph_runner()


def _approval_index() -> Any:
    from ..hitl import get_approval_index

    return get_approval_index()


def _fw_client() -> Any:
    from ..routers import catalog as catalog_router

    return catalog_router.get_fourthwall_client()


def _collections_store() -> Any:
    from ..routers import collections as collections_router

    return collections_router.get_collections_store()


def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Invoke a router endpoint function, mapping HTTP errors to tool errors."""
    try:
        return fn(*args, **kwargs)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        raise ToolError(detail, exc.status_code) from None


async def runs_list(
    collection: Optional[str] = None,
    status: Optional[str] = None,
    date: Optional[str] = None,
) -> dict[str, Any]:
    """List runs (same shape as GET /api/runs)."""
    require_scope(SCOPE_READ)
    from ..routers import runs as runs_router

    return _call(
        runs_router.list_runs,
        actor=tool_actor(),
        service=_run_service(),
        collection=collection,
        status_filter=status,
        date=date,
    )


async def run_detail(run_id: str) -> dict[str, Any]:
    """One run's detail incl. per-node state (same shape as GET /api/runs/{id})."""
    require_scope(SCOPE_READ)
    from ..routers import runs as runs_router

    return _call(runs_router.get_run, run_id, actor=tool_actor(), service=_run_service())


async def run_logs(
    run_id: str,
    node: Optional[str] = None,
    level: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Per-node log rows for one run (same shape as GET /api/runs/{id}/logs)."""
    require_scope(SCOPE_READ)
    from ..routers import runs as runs_router

    return _call(
        runs_router.get_run_logs,
        run_id,
        actor=tool_actor(),
        service=_run_service(),
        reader=_log_reader(),
        node=node,
        level=level,
        since=since,
        limit=limit,
    )


async def approvals_queue() -> dict[str, Any]:
    """Live approvals queue (same shape as GET /api/approvals)."""
    require_scope(SCOPE_READ)
    from ..routers import approvals as approvals_router

    return _call(approvals_router.list_approvals, actor=tool_actor(), service=_hitl_service())


async def agents_roster() -> list[dict[str, Any]]:
    """Full agent roster with effective config (same shape as GET /api/agents)."""
    require_scope(SCOPE_READ)
    from ..routers import agents as agents_router

    return _call(agents_router.list_agents, actor=tool_actor())


async def models_search(q: Optional[str] = None) -> dict[str, Any]:
    """Model catalog search (same shape as GET /api/agents/models)."""
    require_scope(SCOPE_READ)
    from ..routers import agents as agents_router

    return _call(agents_router.list_catalog_models, q=q, actor=tool_actor())


async def prompt_meta(node: str) -> dict[str, Any]:
    """Prompt key/version/presence for one node (same as GET /api/agents/{node}/prompt)."""
    require_scope(SCOPE_READ)
    from ..routers import agents as agents_router

    return _call(agents_router.get_agent_prompt, node, actor=tool_actor())


async def collection_get(slug: str) -> dict[str, Any]:
    """One collection with its contract (same shape as GET /api/collections/{slug})."""
    require_scope(SCOPE_READ)
    from ..routers import collections as collections_router

    return _call(
        collections_router.get_collection, slug,
        actor=tool_actor(), store=_collections_store(),
    )


async def audit_query(
    actor: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Audit rows newest-first (same rows as GET /api/audit, JSON shape)."""
    require_scope(SCOPE_READ)
    from ..routers import audit as audit_router

    filters = AuditFilters(
        actor=actor, action=action, entity_type=entity_type,
        entity_id=entity_id, limit=limit,
    )
    return _call(audit_router.list_audit, actor=tool_actor(), reader=_audit_reader(),
                 filter_actor=filters.actor, action=filters.action,
                 entity_type=filters.entity_type, entity_id=filters.entity_id,
                 limit=filters.limit)


async def calibration_get(design_id: str) -> dict[str, Any]:
    """Rubric-vs-human calibration for one design (same as GET .../calibration)."""
    require_scope(SCOPE_READ)
    from ..routers import designs as designs_router

    return _call(
        designs_router.get_design_calibration, design_id,
        actor=tool_actor(), runner=_graph_runner(), index=_approval_index(),
    )


READ_TOOLS = (
    runs_list,
    run_detail,
    run_logs,
    approvals_queue,
    agents_roster,
    models_search,
    prompt_meta,
    collection_get,
    audit_query,
    calibration_get,
)
