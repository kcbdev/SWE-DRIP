"""Agents API — roster, model catalog, per-node config (FR-17, C4 + control plane).

GET  /api/agents                — full roster (Viewer+)
GET  /api/agents/models         — OpenRouter catalog list, ?q= filter (Viewer+)
GET  /api/agents/models/{id}    — one catalog entry (Viewer+)
GET  /api/agents/{node}         — single agent detail (Viewer+)
GET  /api/agents/{node}/prompt  — prompt key/version/override presence (Viewer+)
PATCH /api/agents/{node}/config — budget cap, model, params, enabled and/or
  prompt_override edit (Admin, cost-impact note required)

Model routing defaults live in ``pipeline/routing.py``; an operator override in
the settings store (``node_config``) wins at run start (agent-control-plane C1).
A model may only be saved when its ID is present in the live catalog (C3).
Prompt overrides are plain text (spec C6 — never executed); only the four
prompted nodes accept one, and prompt *text* never travels in a response —
only key/version/presence (spec C4 secrets rule).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from .. import model_catalog
from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, ROLE_VIEWER, Actor
from ..rbac import require_role
from ..agents import (
    AgentInfo,
    GLOBAL_MONTHLY_CAP,
    get_agent_detail,
    get_budget_caps,
    get_roster,
    set_budget_cap,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_VIEWER))
AdminOnly = Depends(require_role(ROLE_ADMIN))


def _agent_to_dict(a: AgentInfo) -> dict[str, Any]:
    return {
        "node": a.node,
        "role": a.role,
        "model": a.model,
        "model_source": a.model_source,
        "params": dict(a.params or {}),
        "enabled": a.enabled,
        "overridden": list(a.overridden),
        "prompt_key": a.prompt_key,
        "prompt_version": a.prompt_version,
        "has_prompt_override": a.has_prompt_override,
        "cap_usd": a.cap_usd,
        "spend_usd": a.spend_usd,
        "routing_edit": "pipeline/routing.py",
    }


@router.get("")
def list_agents(actor: Actor = ReadAllowed) -> list[dict[str, Any]]:
    """Return the full agent roster."""
    return [_agent_to_dict(a) for a in get_roster()]


# NOTE: catalog routes are declared BEFORE "/{node}" so "models" is never
# captured as a node name (FastAPI matches in declaration order).


@router.get("/models")
def list_catalog_models(
    q: Optional[str] = Query(default=None, description="Substring filter on id/name"),
    actor: Actor = ReadAllowed,
) -> dict[str, Any]:
    """Catalog list for the UI picker (Viewer+). Never 500s on catalog trouble.

    Shape: ``{"models": [{id, name, context_length, prompt/completion price per
    M, input modalities}], "stale": bool, "unavailable": bool}``. When the
    catalog has never been fetched and the live fetch fails, ``models`` is
    empty and ``unavailable`` is True — the UI disables editing with a visible
    reason rather than offering free text (PBI-041 refinement rule).
    """
    models, catalog_status = model_catalog.list_models(query=q)
    return {
        "models": models,
        "stale": bool(catalog_status.get("stale")),
        "unavailable": bool(catalog_status.get("unavailable")),
    }


@router.get("/models/{model_id:path}")
def get_catalog_model(model_id: str, actor: Actor = ReadAllowed) -> dict[str, Any]:
    """One catalog entry by exact ID (Viewer+)."""
    row = model_catalog.get_model(model_id)
    if row is not None:
        _, catalog_status = model_catalog.list_models()
        return {
            **row,
            "stale": bool(catalog_status.get("stale")),
            "unavailable": bool(catalog_status.get("unavailable")),
        }
    _, catalog_status = model_catalog.list_models()
    if catalog_status.get("unavailable"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenRouter model catalog cannot be verified right now; try again later",
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "message": f"Unknown model: {model_id}",
            "suggestions": model_catalog.closest(model_id),
        },
    )


@router.get("/{node}")
def get_agent(node: str, actor: Actor = ReadAllowed) -> dict[str, Any]:
    """Return detail for a single agent."""
    agent = get_agent_detail(node)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown node: {node}")
    return _agent_to_dict(agent)


@router.get("/{node}/prompt")
def get_agent_prompt(node: str, actor: Actor = ReadAllowed) -> dict[str, Any]:
    """Prompt key/version/override presence for one node (Viewer+).

    Prompt *text* never travels here (spec C4 secrets rule) — the editor UI
    shows key + versions + presence, and the override is write-only.
    Non-prompted nodes (no model prompt to override) return nulls.
    """
    from pipeline.prompts import BASE_VERSIONS, PROMPT_KEYS, prompt_version

    agent = get_agent_detail(node)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown node: {node}")
    key = PROMPT_KEYS.get(node)
    if key is None:
        return {"node": node, "prompt_key": None, "base_version": None,
                "prompt_version": None, "has_override": False, "override_chars": 0}
    from ..settings_store import get_node_config_override

    raw = get_node_config_override(node).get("prompt_override")
    override = raw if isinstance(raw, str) and raw.strip() else None
    return {
        "node": node,
        "prompt_key": key,
        "base_version": BASE_VERSIONS[key],
        "prompt_version": prompt_version(node, override),
        "has_override": override is not None,
        "override_chars": len(override) if override is not None else 0,
    }


class AgentConfigPatch(BaseModel):
    cap_usd: Optional[float] = None
    model: Optional[str] = None
    params: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None
    prompt_override: Optional[str] = None
    cost_impact_note: str  # required — budget discipline, AGENTS.md §3


# Generation params the UI may set (PBI-041). Anything else is rejected so a
# typo cannot write junk the pipeline would silently ignore.
_ALLOWED_PARAMS = ("temperature", "max_tokens")


def _validate_params(params: dict[str, Any]) -> dict[str, Any]:
    """Validate a params patch; raises HTTPException 400 on any problem."""
    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if key not in _ALLOWED_PARAMS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown param: {key} (allowed: {', '.join(_ALLOWED_PARAMS)})",
            )
        if key == "temperature":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="temperature must be a number between 0 and 2",
                )
            if not 0 <= float(value) <= 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="temperature must be a number between 0 and 2",
                )
            cleaned[key] = float(value)
        elif key == "max_tokens":
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="max_tokens must be a positive integer",
                )
            cleaned[key] = value
    return cleaned


@router.patch("/{node}/config")
def patch_agent_config(
    node: str,
    body: AgentConfigPatch,
    actor: Actor = AdminOnly,
    audit: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Update a node's budget cap, model, params, enabled flag and/or prompt
    override. Requires Admin + cost-impact note.

    Model enforcement (spec C3): the ID must be present in the live OpenRouter
    catalog. A dead ID is rejected with 422 + closest matches; when the catalog
    cannot be verified the write is refused (503) rather than accepted blindly.
    Params are limited to temperature (0-2) and max_tokens (positive int).
    Prompt overrides (spec C4) are accepted only for the four prompted nodes;
    the audit row records versions, never the override text.
    An explicit ``null`` clears that field's store override (falls back to the
    code default); an omitted field leaves it untouched.
    """
    agent = get_agent_detail(node)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown node: {node}")

    if not body.cost_impact_note or not body.cost_impact_note.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cost_impact_note is required",
        )
    note = body.cost_impact_note.strip()

    fields_set = body.model_fields_set
    wants_cap = body.cap_usd is not None
    wants_model = "model" in fields_set
    wants_params = "params" in fields_set
    wants_enabled = "enabled" in fields_set
    wants_prompt = "prompt_override" in fields_set

    if not wants_cap and not wants_model and not wants_params and not wants_enabled and not wants_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No config fields supplied (cap_usd, model, params, enabled and/or prompt_override)",
        )

    if wants_cap:
        assert body.cap_usd is not None
        if body.cap_usd < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Budget cap must be non-negative",
            )
        if body.cap_usd > GLOBAL_MONTHLY_CAP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Budget cap {body.cap_usd} exceeds global monthly cap {GLOBAL_MONTHLY_CAP}",
            )

    new_model: Optional[str] | None = None
    clear_model = False
    if wants_model:
        if body.model is None:
            clear_model = True
        elif not body.model.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="model must be a non-empty ID or null to clear the override",
            )
        else:
            candidate = body.model.strip()
            try:
                model_catalog.verify_for_write(candidate)
            except model_catalog.CatalogUnavailable as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from None
            except LookupError as exc:
                suggestions = exc.args[1] if len(exc.args) > 1 else model_catalog.closest(candidate)
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": f"Unknown model: {candidate}",
                        "suggestions": list(suggestions),
                    },
                ) from None
            new_model = candidate

    new_params: Optional[dict[str, Any]] = None
    clear_params = False
    if wants_params:
        if body.params is None:
            clear_params = True
        elif not isinstance(body.params, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="params must be an object or null to clear the override",
            )
        else:
            new_params = _validate_params(body.params)

    new_enabled: Optional[bool] = None
    clear_enabled = False
    if wants_enabled:
        if body.enabled is None:
            clear_enabled = True
        elif not isinstance(body.enabled, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="enabled must be true, false, or null to clear the override",
            )
        else:
            new_enabled = body.enabled

    new_prompt: Optional[str] | None = None
    clear_prompt = False
    if wants_prompt:
        from pipeline.prompts import PROMPT_KEYS

        if node not in PROMPT_KEYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{node} takes no prompt override "
                       f"(prompted nodes: {', '.join(sorted(PROMPT_KEYS))})",
            )
        if body.prompt_override is None:
            clear_prompt = True
        elif not body.prompt_override.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="prompt_override must be non-empty text or null to clear the override",
            )
        else:
            new_prompt = body.prompt_override

    if wants_cap:
        assert body.cap_usd is not None
        before_cap = get_budget_caps().get(node, 50.0)
        set_budget_cap(node, body.cap_usd)
        after_cap = get_budget_caps().get(node, 50.0)
        audit.record(
            action="agents.budget_cap.update",
            entity_type="agent",
            entity_id=node,
            before={"cap_usd": before_cap, "cost_impact_note": None},
            after={"cap_usd": after_cap, "cost_impact_note": note},
            actor_user_id=actor.user_id,
        )

    if wants_model:
        from ..settings_store import get_node_config_override, set_node_config_override

        before_model = get_node_config_override(node).get("model")
        if clear_model:
            set_node_config_override(node, {"model": None})
            after_model: Any = None
        else:
            assert new_model is not None
            set_node_config_override(node, {"model": new_model})
            after_model = new_model
        audit.record(
            action="agents.model.update",
            entity_type="agent",
            entity_id=node,
            before={"model": before_model, "cost_impact_note": None},
            after={"model": after_model, "cost_impact_note": note},
            actor_user_id=actor.user_id,
        )

    if wants_params or wants_enabled:
        from ..settings_store import get_node_config_override, set_node_config_override

        if wants_params:
            before_params = get_node_config_override(node).get("params")
            if clear_params:
                set_node_config_override(node, {"params": None})
                after_params: Any = None
            else:
                assert new_params is not None
                set_node_config_override(node, {"params": new_params})
                after_params = new_params
            audit.record(
                action="agents.params.update",
                entity_type="agent",
                entity_id=node,
                before={"params": before_params, "cost_impact_note": None},
                after={"params": after_params, "cost_impact_note": note},
                actor_user_id=actor.user_id,
            )
        if wants_enabled:
            before_enabled = get_node_config_override(node).get("enabled")
            if clear_enabled:
                set_node_config_override(node, {"enabled": None})
                after_enabled: Any = None
            else:
                assert new_enabled is not None
                set_node_config_override(node, {"enabled": new_enabled})
                after_enabled = new_enabled
            audit.record(
                action="agents.enabled.update",
                entity_type="agent",
                entity_id=node,
                before={"enabled": before_enabled, "cost_impact_note": None},
                after={"enabled": after_enabled, "cost_impact_note": note},
                actor_user_id=actor.user_id,
            )

    if wants_prompt:
        from pipeline.prompts import prompt_version as _prompt_version

        from ..settings_store import get_node_config_override, set_node_config_override

        before_raw = get_node_config_override(node).get("prompt_override")
        before_version = _prompt_version(
            node, before_raw if isinstance(before_raw, str) else None)
        if clear_prompt:
            set_node_config_override(node, {"prompt_override": None})
            after_version = _prompt_version(node, None)
        else:
            assert new_prompt is not None
            set_node_config_override(node, {"prompt_override": new_prompt})
            after_version = _prompt_version(node, new_prompt)
        # Versions travel, never the override text (spec C4 secrets rule).
        audit.record(
            action="agents.prompt.update",
            entity_type="agent",
            entity_id=node,
            before={"prompt_version": before_version, "cost_impact_note": None},
            after={"prompt_version": after_version, "cost_impact_note": note},
            actor_user_id=actor.user_id,
        )

    refreshed = get_agent_detail(node)
    assert refreshed is not None
    return _agent_to_dict(refreshed)
