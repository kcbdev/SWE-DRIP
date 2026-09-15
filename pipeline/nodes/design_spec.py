"""Node 4 — design spec (spec C2/C3/C4, parity shape C7).

Resolves the per-design brief against the ACTIVE collection contract for
creative-direction reasoning (RCAO via the routed model), but style, palette,
and placement templates are INHERITED — forced from the contract in code after
the model call, never re-decided per design. A model that suggests a different
style is overruled deterministically (asserted in tests).
"""

from __future__ import annotations

from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..costs import build_cost_record, record_cost
from ..graph import DEFAULT_HITL, register_node
from ..json_parse import parse_json_object
from ..node_config import effective_for_config
from ..routing import model_for
from ..state import RunState

NODE = "design_spec"

# Inherited verbatim from the contract — the only legal source for these keys.
INHERITED_KEYS = ("style", "palette", "placement_templates")


def design_spec(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Node 4 implementation: RCAO reasoning → forced inheritance → cost-log."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})

    brief = state.get("brief")
    contract = state.get("collection_contract")
    if not brief:
        return {"design_spec": {}, "visited": [NODE], "errors": [f"{NODE}: no design brief in state"]}
    if not contract:
        return {
            "design_spec": {},
            "visited": [NODE],
            "errors": [f"{NODE}: no collection contract in state"],
        }
    client = cfg.get("llm_client")
    if client is None:
        raise RuntimeError(
            "design_spec: no llm_client in config['configurable'] "
            "(the production runner injects OpenRouterClient)"
        )
    conf = effective_for_config(cfg, NODE)
    if not conf.enabled:
        return {
            "design_spec": {"skipped": True, "reason": "disabled by node config"},
            "visited": [NODE],
        }
    model = conf.model or model_for(NODE)
    assert model is not None  # routed per §3; None would be a routing-table bug
    prompt = (
        "Using the RCAO framework (Reason, Creative direction, Audience, Output), "
        "reason about this t-shirt design and propose a render prompt. Reply ONLY "
        "with JSON: {\"rcao\": string, \"render_prompt\": string}.\n"
        f"Brief subject: {brief.get('subject', '')}\nBrief text: {brief.get('text', '')}\n"
        f"Collection theme: {contract.get('theme', '')}\n"
        f"Locked style: {contract.get('style_archetype', '')}"
    )
    result = client.chat(
        model=model, messages=[{"role": "user", "content": prompt}], **conf.params
    )
    try:
        reasoning = parse_json_object(result.content)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"design_spec: model did not return JSON: {exc}") from None
    if not isinstance(reasoning, dict) or not reasoning.get("render_prompt"):
        raise ValueError("design_spec: model returned no render_prompt")

    spec = {
        "design_id": state.get("design_id", ""),
        "collection_id": contract.get("collection_id", state.get("collection_id", "")),
        "brief_subject": brief.get("subject", ""),
        # Forced inheritance — whatever the model suggested is discarded:
        "style": contract.get("style_archetype"),
        "palette": (contract.get("illustration_rules") or {}).get("palette", []),
        "placement_templates": contract.get("placement_templates", []),
        "render_prompt": reasoning["render_prompt"],
        "rcao": reasoning.get("rcao", ""),
    }

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

    output: dict[str, Any] = {"design_spec": spec, "visited": [NODE]}
    if errors:
        output["errors"] = errors
    return output


register_node(NODE, design_spec)
