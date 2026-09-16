"""Node 3 — listing copy (spec C2/C3/C4).

Generates slogan/title/description/tags via the routed model, then enforces
the BRAND-LOCKED constraints in code (never trusted from the model):
slogan ≤ 6 words, title ≤ 60 chars, description non-empty, tags non-empty,
no hashtags anywhere. Violations are loud (``ValueError``) — locked copy must
never flow downstream silently (relaxations need founder spec change).
"""

from __future__ import annotations

from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..costs import build_cost_record, record_cost
from ..graph import DEFAULT_HITL, register_node
from ..json_parse import parse_json_object
from ..node_config import effective_for_config
from ..prompts import build_copy_prompt, effective_prompt
from ..routing import model_for
from ..runlog import get_logger
from ..state import RunState

NODE = "listing_copy"

SLOGAN_MAX_WORDS = 6
TITLE_MAX_CHARS = 60


def validate_copy(copy: dict[str, Any]) -> list[str]:
    """Brand-lock checks. Returns error strings (empty = valid)."""
    errors: list[str] = []
    if not isinstance(copy, dict):
        return ["copy must be a mapping"]
    slogan = copy.get("slogan")
    if not isinstance(slogan, str) or not slogan.strip():
        errors.append("slogan must be a non-empty string")
    elif len(slogan.split()) > SLOGAN_MAX_WORDS:
        errors.append(f"slogan must be ≤ {SLOGAN_MAX_WORDS} words")
    title = copy.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("title must be a non-empty string")
    elif len(title) > TITLE_MAX_CHARS:
        errors.append(f"title must be ≤ {TITLE_MAX_CHARS} characters")
    description = copy.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("description must be a non-empty string")
    tags = copy.get("tags")
    if not isinstance(tags, list) or not tags or not all(isinstance(t, str) and t.strip() for t in tags):
        errors.append("tags must be a non-empty list of strings")
    for field in ("slogan", "title", "description"):
        value = copy.get(field)
        if isinstance(value, str) and "#" in value:
            errors.append(f"{field} must not contain hashtags")
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.lstrip().startswith("#"):
                errors.append("tags must not contain hashtags")
                break
    return errors


def listing_copy(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Node 3 implementation: generate → brand-lock validate → cost-log."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})

    brief = state.get("brief")
    if not brief:
        get_logger(cfg).error(NODE, "no design brief in state",
                              run_id=str(cfg.get("thread_id") or ""))
        return {
            "listing_copy": {},
            "visited": [NODE],
            "errors": [f"{NODE}: no design brief in state"],
        }
    client = cfg.get("llm_client")
    if client is None:
        raise RuntimeError(
            "listing_copy: no llm_client in config['configurable'] "
            "(the production runner injects OpenRouterClient)"
        )
    conf = effective_for_config(cfg, NODE)
    log = get_logger(cfg)
    rid = str(cfg.get("thread_id") or "")
    if not conf.enabled:
        log.warn(NODE, "skipped — disabled by node config", run_id=rid)
        return {
            "listing_copy": {"skipped": True, "reason": "disabled by node config"},
            "visited": [NODE],
        }
    model = conf.model or model_for(NODE)
    assert model is not None  # routed per §3; None would be a routing-table bug
    log.info(NODE, f"writing copy with {model}", run_id=rid,
             detail={"model": model, "params": conf.params})
    prompt = effective_prompt(NODE, build_copy_prompt(brief), conf.prompt_override)
    result = client.chat(
        model=model, messages=[{"role": "user", "content": prompt}], **conf.params
    )
    try:
        copy = parse_json_object(result.content)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"listing_copy: model did not return JSON: {exc}") from None
    violations = validate_copy(copy)
    if violations:  # brand-locked: never propagate silently
        log.error(NODE, f"brand-lock violations: {violations!r}", run_id=rid)
        raise ValueError(f"listing_copy: brand-lock violations: {violations!r}")

    errors: list[str] = []
    usage = result.raw.get("usage") or {}
    record = build_cost_record(
        NODE,
        model,
        int(usage.get("prompt_tokens") or 0),
        int(usage.get("completion_tokens") or 0),
        float(usage.get("cost") or 0.0),
    )
    engine = cfg.get("cost_engine")
    if engine is None:
        errors.append(f"{NODE}: cost row not written (no cost_engine configured)")
    else:
        outcome = record_cost(record, engine)
        if not outcome.ok:
            errors.append(f"{NODE}: cost logging failed: {outcome.error}")

    output: dict[str, Any] = {"listing_copy": copy, "visited": [NODE]}
    if errors:
        output["errors"] = errors
        log.warn(NODE, f"cost row not recorded: {errors[0]}", run_id=rid)
    else:
        log.info(NODE, f"copy accepted: {copy.get('slogan')!r}", run_id=rid)
    return output


register_node(NODE, listing_copy)
