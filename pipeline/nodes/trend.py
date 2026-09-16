"""Node 1 — trend research + clustering (spec C2/C3/C4).

Deterministic scoring with LOCKED weights (PBI-011 refinement rule — changes
require a spec amendment, not a code tweak): engagement 0–40, novelty 0–30,
specificity 0–30, pass ≥ 60. Thematic clustering is one LLM synthesis call per
run (model from routing); trivial inputs skip the call entirely (no synthesis
needed for 0–1 passing briefs). No embeddings/vector search, no pgvector —
LLM + deterministic post-processing only.

Every model call writes a ``model_calls`` row (C4); logging problems are
recorded in ``state["errors"]``, never crash-inducing.
"""

from __future__ import annotations

import json
from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..costs import build_cost_record, record_cost
from ..graph import DEFAULT_HITL, register_node
from ..node_config import effective_for_config
from ..prompts import build_trend_prompt, effective_prompt
from ..routing import model_for
from ..runlog import get_logger
from ..state import RunState

NODE = "trend_research"

# Locked scoring rubric (weights + threshold are spec, not tuning knobs).
MAX_ENGAGEMENT = 40
MAX_NOVELTY = 30
MAX_SPECIFICITY = 30
PASS_THRESHOLD = 60

_SCORE_FIELDS = (
    ("engagement", MAX_ENGAGEMENT),
    ("novelty", MAX_NOVELTY),
    ("specificity", MAX_SPECIFICITY),
)


def score_brief(engagement: float, novelty: float, specificity: float) -> dict[str, Any]:
    """Deterministic rubric score; loud on out-of-range inputs."""
    values = {"engagement": engagement, "novelty": novelty, "specificity": specificity}
    for (field, maximum) in _SCORE_FIELDS:
        value = values[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{field} must be a number, got {value!r}")
        if not 0 <= value <= maximum:
            raise ValueError(f"{field}={value} out of locked range 0–{maximum}")
    total = engagement + novelty + specificity
    return {**values, "total": total, "passed": total >= PASS_THRESHOLD}


def _parse_json_payload(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"clustering synthesis did not return JSON: {exc}") from None


def cluster_briefs(
    briefs: list[dict[str, Any]],
    client: Any,
    model: str,
    params: dict[str, Any] | None = None,
    prompt_override: str | None = None,
) -> tuple[list[dict[str, Any]], Any | None]:
    """Group passing briefs into collection candidates.

    Returns ``(clusters, llm_result)`` where ``llm_result`` is ``None`` when no
    model call was needed. Cluster assignment is deterministic post-processing:
    brief IDs sorted, clusters ordered by (theme, first brief id), stable
    ``cluster-N`` IDs. Unknown brief IDs in the synthesis are loud, not dropped.

    ``prompt_override`` (operator text from the resolved node config) replaces
    the built-in clustering prompt verbatim when set — data, never templated.
    """
    for brief in briefs:
        if not brief.get("id"):
            raise ValueError("every brief needs an 'id' for clustering")
    if not briefs:
        return [], None
    if len(briefs) == 1:
        only = briefs[0]
        theme = str(only.get("subject") or "untitled").strip() or "untitled"
        return [{"cluster_id": "cluster-1", "theme": theme, "brief_ids": [only["id"]]}], None

    prompt = effective_prompt(
        NODE, build_trend_prompt(briefs), prompt_override
    )
    result = client.chat(
        model=model, messages=[{"role": "user", "content": prompt}], **(params or {})
    )
    payload = _parse_json_payload(result.content if isinstance(result.content, str) else "")
    raw_clusters = (payload.get("clusters") if isinstance(payload, dict) else None) or []
    known = {b["id"] for b in briefs}
    normalized = []
    for raw in raw_clusters:
        theme = str(raw.get("theme") or "").strip()
        ids = sorted(set(raw.get("brief_ids") or []))
        unknown = [i for i in ids if i not in known]
        if not theme or not ids:
            raise ValueError(f"clustering synthesis returned an empty cluster: {raw!r}")
        if unknown:
            raise ValueError(f"clustering synthesis referenced unknown brief IDs: {unknown!r}")
        normalized.append((theme, ids))
    normalized.sort(key=lambda item: (item[0].lower(), item[1][0]))
    return [
        {"cluster_id": f"cluster-{n}", "theme": theme, "brief_ids": ids}
        for n, (theme, ids) in enumerate(normalized, start=1)
    ], result


def trend_research(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Node 1 implementation: score → filter → cluster → cost-log."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})
    log = get_logger(cfg)
    rid = str(cfg.get("thread_id") or "")
    briefs = state.get("briefs") or []
    scored = []
    for brief in briefs:
        missing = [key for key, _ in _SCORE_FIELDS if key not in brief]
        if missing:
            raise ValueError(f"brief {brief.get('id', '?')!r} missing score fields: {missing!r}")
        scored.append(
            {
                **brief,
                "score": score_brief(brief["engagement"], brief["novelty"], brief["specificity"]),
            }
        )
    passing = [b for b in scored if b["score"]["passed"]]
    if not passing:
        log.info(NODE, f"scored {len(scored)} briefs, none passing — no model call", run_id=rid)
        return {"clusters": [], "visited": [NODE]}

    client = cfg.get("llm_client")
    if client is None:
        raise RuntimeError(
            "trend_research: no llm_client in config['configurable'] "
            "(the production runner injects OpenRouterClient)"
        )
    # Resolved node config (frozen into the run at start). Absent → code defaults.
    conf = effective_for_config(cfg, NODE)
    if not conf.enabled:
        log.warn(NODE, "skipped — disabled by node config", run_id=rid)
        return {
            "clusters": [{"skipped": True, "reason": "disabled by node config"}],
            "visited": [NODE],
        }
    model = conf.model or model_for(NODE)
    assert model is not None  # routed per §3; None would be a routing-table bug
    log.info(NODE, f"clustering {len(passing)} briefs with {model}",
             run_id=rid, detail={"model": model, "params": conf.params})
    clusters, llm_result = cluster_briefs(passing, client, model, conf.params, conf.prompt_override)

    errors: list[str] = []
    if llm_result is not None:
        usage = llm_result.raw.get("usage") or {}
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

    output: dict[str, Any] = {"clusters": clusters, "visited": [NODE]}
    if errors:
        output["errors"] = errors
        log.warn(NODE, f"cost row not recorded: {errors[0]}", run_id=rid)
    else:
        log.info(NODE, f"{len(clusters)} clusters from {len(passing)} briefs", run_id=rid)
    return output


register_node(NODE, trend_research)
