"""Research node 2 — style synthesis (spec C4).

Proposes the collection's locked directives via the routed model: graphic
vocabulary, motif set, palette justification, and anti-references — with
the lineage ``avoid`` list as negative context. The model proposes within
the locked style vocabulary; minting styles stays human (spec anti-pattern).

Model routing: research nodes are monthly-cadence and outside the item
``node_config`` table, so the model is a routing constant (cheap chat
class) with an explicit config override escape hatch
(``config["configurable"]["research_models"]["style_synthesis"]``).
The effective prompt's sha carries the version (per-run inputs mean
per-run versions — honest for research, where calibration pins do not
apply the way item-QC pins do).
"""

from __future__ import annotations

import hashlib
from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..collection_graph import RESEARCH_DEFAULT_HITL, register_research_node
from ..costs import build_cost_record, record_cost
from ..json_parse import parse_json_object
from ..routing import CLAUDE_SONNET
from ..runlog import get_logger

NODE = "style_synthesis"

# Cheap chat class, same family as the item copy/spec default.
DEFAULT_MODEL = CLAUDE_SONNET


def build_synthesis_prompt(
    inspiration: dict[str, Any],
    avoid: list[str],
    style_names: list[str],
) -> str:
    """Locked-directive proposal prompt (pure — asserted verbatim in tests)."""
    assets = inspiration.get("assets") or []
    refs = inspiration.get("refs") or []
    lines = [
        "Propose locked visual directives for a t-shirt collection. Reply ONLY with JSON: "
        '{"style_descriptors": [string, ...], "motifs": [string, ...], '
        '"palette_justification": string, "avoid": [string, ...]}.',
        f"Locked style vocabulary (choose descriptors inside it, never mint): {', '.join(style_names)}.",
        f"Curated inspiration: {len(assets)} image assets, {len(refs)} link refs.",
    ]
    for ref in refs:
        if isinstance(ref, dict) and ref.get("url"):
            lines.append(f"- ref: {ref['url']} ({ref.get('note', '')})")
    if avoid:
        lines.append(f"Lineage to avoid repeating: {', '.join(avoid)}.")
    lines.append("Do not invent product copy, prices, or placement — directives only.")
    return "\n".join(lines)


def prompt_fingerprint(prompt: str) -> str:
    """Per-run prompt version (inputs differ per run — stable within one)."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


def style_synthesis(
    state: dict[str, Any], config: RunnableConfig = None  # type: ignore[assignment]
) -> dict[str, Any]:
    """Node 2 implementation: propose → validate shape → cost-log."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, RESEARCH_DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})
    log = get_logger(cfg)
    rid = str(cfg.get("thread_id") or "")
    inspiration = state.get("inspiration")
    if not inspiration:
        log.error(NODE, "no reviewed inspiration in state", run_id=rid)
        return {"visited": [NODE], "errors": [f"{NODE}: no reviewed inspiration in state"]}
    client = cfg.get("llm_client")
    if client is None:
        raise RuntimeError(f"{NODE}: no llm_client in config['configurable']")
    from ..styles import style_names

    avoid = [str(a) for a in (state.get("avoid") or []) if a]
    prompt = build_synthesis_prompt(inspiration, avoid, style_names())
    model = ((cfg.get("research_models") or {}).get(NODE)) or DEFAULT_MODEL
    log.info(NODE, f"synthesizing with {model}", run_id=rid, detail={"model": model})
    result = client.chat(model=model, messages=[{"role": "user", "content": prompt}])
    try:
        directives = parse_json_object(result.content)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{NODE}: model did not return JSON: {exc}") from None
    if not isinstance(directives, dict) or not directives.get("style_descriptors"):
        raise ValueError(f"{NODE}: model returned no style_descriptors")
    synthesis = {
        "style_descriptors": directives.get("style_descriptors"),
        "motifs": directives.get("motifs", []),
        "palette_justification": directives.get("palette_justification", ""),
        "avoid": directives.get("avoid", []),
        "model_used": model,
        "prompt_version": prompt_fingerprint(prompt),
    }
    errors: list[str] = []
    usage = result.raw.get("usage") or {}
    record = build_cost_record(
        NODE, model,
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
    output: dict[str, Any] = {"synthesis": synthesis, "visited": [NODE]}
    if errors:
        output["errors"] = errors
    log.info(NODE, f"directives proposed: {synthesis['style_descriptors']!r}", run_id=rid)
    return output


register_research_node(NODE, style_synthesis)
