"""MCP research + styles tools (collection-research UI for agents).

Same doorway discipline as the item tools: every tool calls the router
endpoint function its REST twin calls, with a scope-checked synthesized
actor — shapes identical by construction. Reads need ``read``, writes need
``operate`` (≡ admin downstream, same as the PBI-045 writes).

Covered twins: ``/api/research/*`` (trigger, list/detail, logs,
approvals queue/decision), ``/api/styles`` (list/create/update), and the
board-serve endpoint (bytes as base64 — vision-capable agents can score
the sheet; the SSE log stream has no MCP equivalent, ``research_run_logs``
covers the rows).

Port factories resolve production ports at call time; tests monkeypatch
these module attributes with fakes.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

from .auth import SCOPE_OPERATE, SCOPE_READ, ToolError, require_scope, tool_actor
from .tools_reads import _call, _clamp_limit
from .tools_writes import _audit_writer, _body

BOARD_BYTES_LIMIT = 5 * 1024 * 1024


def _research_ports() -> Any:
    from ..research_runs import ResearchRunPorts

    return ResearchRunPorts()


def _research_starter() -> Any:
    from ..routers import research as research_router

    return research_router.get_research_starter()


def _research_runner() -> Any:
    from ..research_runs import ResearchGraphRunner

    return ResearchGraphRunner()


def _research_gates() -> Any:
    from ..routers import research as research_router

    return research_router.get_research_gates()


def _research_index() -> Any:
    from ..hitl import get_approval_index

    return get_approval_index()


def _research_service() -> Any:
    from ..hitl import HitlService

    return HitlService(
        gates=_research_gates(),
        index=_research_index(),
        runner=_research_runner(),
        writer=_audit_writer(),
    )


def _spend_reader() -> Any:
    from ..routers import runs as runs_router

    return runs_router.get_spend_reader()


def _log_reader() -> Any:
    from ..routers import runs as runs_router

    return runs_router.get_log_reader()


def _collections_store() -> Any:
    from ..routers import collections as collections_router

    return collections_router.get_collections_store()


def _styles_store() -> Any:
    from ..routers import styles as styles_router

    return styles_router.get_styles_store()


# ---------------------------------------------------------------- reads


async def research_runs_list() -> dict[str, Any]:
    """Research runs newest-first (same shape as GET /api/research/runs)."""
    require_scope(SCOPE_READ)
    from ..routers import research as research_router

    return _call(
        research_router.list_research,
        actor=tool_actor(),
        ports=_research_ports(),
    )


async def research_run_detail(run_id: str) -> dict[str, Any]:
    """One research run: stage, board, flags, draft, gate (same as GET .../runs/{id})."""
    require_scope(SCOPE_READ)
    from ..routers import research as research_router

    return _call(
        research_router.get_research_run,
        run_id,
        actor=tool_actor(),
        ports=_research_ports(),
    )


async def research_run_logs(
    run_id: str,
    node: Optional[str] = None,
    level: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Per-node log rows for one research run (same as GET .../runs/{id}/logs)."""
    require_scope(SCOPE_READ)
    from ..routers import research as research_router

    return _call(
        research_router.get_research_logs,
        run_id,
        actor=tool_actor(),
        ports=_research_ports(),
        reader=_log_reader(),
        node=node,
        level=level,
        since=since,
        limit=_clamp_limit(limit, 1, 1000, "limit"),
    )


async def research_approvals_queue() -> dict[str, Any]:
    """Open research gates: draft + board + diversity flags (same as GET /api/research/approvals)."""
    require_scope(SCOPE_READ)
    from ..routers import research as research_router

    return _call(
        research_router.list_research_approvals,
        actor=tool_actor(),
        service=_research_service(),
    )


async def styles_list() -> dict[str, Any]:
    """Locked brand styles with repo version (same shape as GET /api/styles)."""
    require_scope(SCOPE_READ)
    from ..routers import styles as styles_router

    return _call(
        styles_router.list_styles,
        actor=tool_actor(),
        store=_styles_store(),
    )


async def board_file(slug: str, ref: str) -> dict[str, Any]:
    """One mood-board image as base64 (same bytes as GET .../board/{ref}).

    Boards render before any contract names them, so this is scoped to the
    collection's asset dir like the REST twin — relative refs only, images
    only, 5 MB cap.
    """
    require_scope(SCOPE_READ)
    from fastapi.responses import Response

    from ..routers import collections as collections_router

    response = _call(
        collections_router.get_board_file,
        slug,
        ref,
        actor=tool_actor(),
        store=_collections_store(),
    )
    if not isinstance(response, Response):
        raise ToolError("board endpoint returned a non-file payload", 500)
    body = response.body
    if len(body) > BOARD_BYTES_LIMIT:
        raise ToolError(f"board exceeds {BOARD_BYTES_LIMIT} bytes", 422)
    return {
        "slug": slug,
        "ref": ref,
        "media_type": response.media_type,
        "size_bytes": len(body),
        "content_base64": base64.b64encode(body).decode("ascii"),
    }


# ---------------------------------------------------------------- writes


async def research_start(collection_slug: str) -> dict[str, Any]:
    """Start a collection-research run (same guards as POST /api/research/runs).

    Explicit, cost-guarded, audited. Refuses when nothing is curated for
    the draft (422) — curate inspiration first.
    """
    require_scope(SCOPE_OPERATE)
    from ..routers import research as research_router

    return _call(
        research_router.start_research_run,
        _body(research_router.ResearchStartBody, collection_slug=collection_slug),
        actor=tool_actor(),
        starter=_research_starter(),
        spend=_spend_reader(),
        writer=_audit_writer(),
    )


async def research_approval_decide(
    item_id: int,
    action: str,
    note: Optional[str] = None,
    selection: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Decide a research gate (same exactly-once path as POST .../approvals/.../decision).

    ``selection.contract`` carries the CEO edit for edit-and-approve; without
    it an ambiguous gate stays 422, exactly like REST.
    """
    require_scope(SCOPE_OPERATE)
    from ..routers import approvals as approvals_router
    from ..routers import research as research_router

    return _call(
        research_router.decide_research_approval,
        item_id,
        _body(approvals_router.DecisionBody, action=action, note=note,
              selection=selection),
        actor=tool_actor(),
        service=_research_service(),
        ports=_research_ports(),
        store=_collections_store(),
        writer=_audit_writer(),
    )


async def style_create(
    name: str,
    graphic_definition: str,
    expected_version: int,
) -> dict[str, Any]:
    """Append a brand style (same validation as POST /api/styles).

    409 on duplicate name or stale version; the response carries the C1
    revalidation report (affected contracts, possibly empty).
    """
    require_scope(SCOPE_OPERATE)
    from ..routers import styles as styles_router

    return _call(
        styles_router.create_style,
        _body(styles_router.StyleCreateBody, name=name,
              graphic_definition=graphic_definition, expected_version=expected_version),
        actor=tool_actor(),
        store=_styles_store(),
        collections=_collections_store(),
        writer=_audit_writer(),
    )


async def style_update(
    name: str,
    expected_version: int,
    new_name: Optional[str] = None,
    graphic_definition: Optional[str] = None,
) -> dict[str, Any]:
    """Rename and/or redefine a brand style (same validation as PATCH .../{name})."""
    require_scope(SCOPE_OPERATE)
    from ..routers import styles as styles_router

    return _call(
        styles_router.update_style,
        name,
        _body(styles_router.StyleUpdateBody, name=new_name,
              graphic_definition=graphic_definition, expected_version=expected_version),
        actor=tool_actor(),
        store=_styles_store(),
        collections=_collections_store(),
        writer=_audit_writer(),
    )


RESEARCH_READ_TOOLS = (
    research_runs_list,
    research_run_detail,
    research_run_logs,
    research_approvals_queue,
    styles_list,
    board_file,
)

RESEARCH_WRITE_TOOLS = (
    research_start,
    research_approval_decide,
    style_create,
    style_update,
)
