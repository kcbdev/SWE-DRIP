"""Node 3 — listing copy (spec C2/C3/C4).

Generates slogan/title/description/tags via the routed model, then enforces
the BRAND-LOCKED constraints in code (never trusted from the model):
slogan ≤ 6 words, title ≤ 60 chars, description non-empty, tags non-empty,
no hashtags anywhere. Violations are loud (``ValueError``) — locked copy must
never flow downstream silently (relaxations need founder spec change).
"""

from __future__ import annotations

import json
from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..costs import build_cost_record, record_cost
from ..graph import DEFAULT_HITL, register_node
from ..routing import model_for
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
    model = model_for(NODE)
    assert model is not None  # routed per §3; None would be a routing-table bug
    prompt = (
        "Write t-shirt listing copy in a dry developer-identity brand voice. "
        "Reply ONLY with JSON: "
        '{"slogan": "≤6 words, no hashtags", "title": "≤60 chars, no hashtags", '
        '"description": "1-3 sentences, no hashtags", "tags": ["kebab-case tags, no #"]}.\n'
        f"Subject: {brief.get('subject', '')}\nText: {brief.get('text', '')}\n"
        f"Style: {brief.get('style', '')}"
    )
    result = client.chat(model=model, messages=[{"role": "user", "content": prompt}])
    try:
        copy = json.loads(result.content if isinstance(result.content, str) else "")
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"listing_copy: model did not return JSON: {exc}") from None
    violations = validate_copy(copy)
    if violations:  # brand-locked: never propagate silently
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
    return output


register_node(NODE, listing_copy)
