"""MCP write tools (operator-mcp C3) — production writes, same enforcement.

Every tool calls the same router endpoint function the HTTP route calls, with
a scope-checked synthesized actor: validation, cost guards, and audit rows
are identical by construction. Scope model (reconciled per the PBI-044
review): the ``operate`` scope check at the tool boundary IS the
authorization — token issuance by an admin is the human gate, and audit rows
carry the token identity. The synthesized downstream role only satisfies the
router functions' role parameters (bypassed by direct calls, like the reads).

Clearing semantics: MCP schemas cannot distinguish omitted from null, so
nullable clears go through the explicit ``clear`` list (subset of
``model``, ``params``, ``enabled``, ``prompt_override``). A field both set
and cleared is a 422.
"""

from __future__ import annotations

from typing import Any, Optional

from .auth import SCOPE_OPERATE, ToolError, require_scope, tool_actor
from .tools_reads import _call, _hitl_service, _run_service


def _audit_writer() -> Any:
    from ..audit import get_audit_writer

    return get_audit_writer()


def _spend_reader() -> Any:
    from ..routers import runs as runs_router

    return runs_router.get_spend_reader()


def _run_starter() -> Any:
    from ..routers import runs as runs_router

    return runs_router.get_run_starter()


_CLEARABLE = ("model", "params", "enabled", "prompt_override")


def _body(cls: Any, **kwargs: Any) -> Any:
    """Build a router Body model; shape errors are 422s, never crashes."""
    try:
        return cls(**kwargs)
    except Exception as exc:
        raise ToolError(f"invalid request: {exc}", 422) from None


async def run_start(
    collection_id: str,
    briefs: list[dict[str, Any]],
    design_id: Optional[str] = None,
    design_type: Optional[str] = None,
) -> dict[str, Any]:
    """Start a pipeline run (explicit admin action; same guards as POST /api/runs)."""
    require_scope(SCOPE_OPERATE)
    from ..routers import runs as runs_router

    return _call(
        runs_router.start_run,
        _body(
            runs_router.StartBody,
            collection_id=collection_id,
            design_id=design_id,
            briefs=briefs,
            design_type=design_type,
        ),
        actor=tool_actor(),
        starter=_run_starter(),
        spend=_spend_reader(),
        writer=_audit_writer(),
    )


async def approval_decide(
    item_id: int,
    action: str,
    note: Optional[str] = None,
) -> dict[str, Any]:
    """Decide a queued approval (same exactly-once path as POST .../decision)."""
    require_scope(SCOPE_OPERATE)
    from ..routers import approvals as approvals_router

    return _call(
        approvals_router.decide_approval,
        item_id,
        _body(approvals_router.DecisionBody, action=action, note=note),
        actor=tool_actor(),
        service=_hitl_service(),
    )


async def agent_config(
    node: str,
    cost_impact_note: str,
    cap_usd: Optional[float] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    enabled: Optional[bool] = None,
    prompt_override: Optional[str] = None,
    clear: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Patch one node's runtime config (same validation as PATCH .../config).

    Temperature/max_tokens assemble the ``params`` object (the only allowed
    keys). Nullable fields clear via ``clear`` (a set value and a clear for
    the same field is a 422). ``cost_impact_note`` is always required.
    """
    require_scope(SCOPE_OPERATE)
    from ..routers import agents as agents_router

    clear_fields = list(clear or [])
    unknown = [c for c in clear_fields if c not in _CLEARABLE]
    if unknown:
        raise ToolError(f"clear must be a subset of {list(_CLEARABLE)!r}", 422)
    patch: dict[str, Any] = {"cost_impact_note": cost_impact_note}
    if cap_usd is not None:
        patch["cap_usd"] = cap_usd
    if model is not None:
        if "model" in clear_fields:
            raise ToolError("model is both set and cleared", 422)
        patch["model"] = model
    params: dict[str, Any] = {}
    if temperature is not None:
        params["temperature"] = temperature
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    if params:
        if "params" in clear_fields:
            raise ToolError("params is both set and cleared", 422)
        patch["params"] = params
    if enabled is not None:
        if "enabled" in clear_fields:
            raise ToolError("enabled is both set and cleared", 422)
        patch["enabled"] = enabled
    if prompt_override is not None:
        if "prompt_override" in clear_fields:
            raise ToolError("prompt_override is both set and cleared", 422)
        patch["prompt_override"] = prompt_override
    for field in clear_fields:
        patch[field] = None
    body = _body(agents_router.AgentConfigPatch, **patch)
    result = _call(
        agents_router.patch_agent_config,
        node,
        body,
        actor=tool_actor(),
        audit=_audit_writer(),
    )
    return result


async def run_replay(run_id: str, node: str) -> dict[str, Any]:
    """Replay a run from one node (same idempotent-safe path as POST .../replay)."""
    require_scope(SCOPE_OPERATE)
    from ..routers import runs as runs_router

    return _call(
        runs_router.replay_run,
        run_id,
        _body(runs_router.ReplayBody, node=node),
        actor=tool_actor(),
        service=_run_service(),
    )


WRITE_TOOLS = (
    run_start,
    approval_decide,
    agent_config,
    run_replay,
)
