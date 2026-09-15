"""Node 7 — aesthetic QC (spec C9, C2/C3/C4).

Vision model scores the render against the four-criterion rubric (70 pass).
Pass continues. Fail sets ``state["render_feedback"]`` (rejection notes) and
the graph edge routes back to the render node — capped at
``MAX_REGEN_RETRIES`` regenerations. Exhausted retries fall to a
human-review ``interrupt()``; on resume the run continues to technical QC
(human owns the verdict from there; reject/stop semantics belong to the
resume service, PBI-016).

Attempts persist across regen cycles in ``aesthetic_qc.attempts`` (declared
state — no new keys smuggled through the graph).
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from langgraph.types import RunnableConfig, interrupt

from .. import rubric
from ..costs import build_cost_record, record_cost
from ..graph import DEFAULT_HITL, register_node
from ..json_parse import parse_json_object
from ..node_config import effective_for_config
from ..routing import model_for
from ..state import RunState

NODE = "aesthetic_qc"


def image_ref(file_url: str) -> str:
    """Return something OpenRouter accepts as an image URL.

    The render node records a LOCAL artifact path (`runs/<design>/render.png`),
    not a URL, and the vision endpoint rejects a bare path with HTTP 400 — which
    is exactly how the first live run died at aesthetic QC. Local artifacts are
    inlined as a base64 data URI; anything already addressable passes through.
    """
    if file_url.startswith(("http://", "https://", "data:")):
        return file_url
    path = Path(file_url)
    if not path.is_file():
        raise ValueError(f"aesthetic_qc: render artifact not found: {file_url!r}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def aesthetic_qc(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Node 7 implementation: score → pass / regen / human review."""
    cfg = (config or {}).get("configurable") or {}
    # Note: the default-on gate pauses only on exhaustion (below), not on
    # entry. On human resume the node re-executes once (one extra scoring
    # call) and the already-fired interrupt returns the resume value.
    render = state.get("render_result") or {}
    if not render or not render.get("file_url"):
        return {
            "aesthetic_qc": {"result": "fail", "reason": "no render", "attempts": 1},
            "visited": [NODE],
            "errors": [f"{NODE}: no render artifact in state"],
        }
    client = cfg.get("llm_client")
    if client is None:
        raise RuntimeError(
            "aesthetic_qc: no llm_client in config['configurable'] "
            "(the production runner injects OpenRouterClient)"
        )
    conf = effective_for_config(cfg, NODE)
    if not conf.enabled:
        return {
            "aesthetic_qc": {"skipped": True, "reason": "disabled by node config"},
            "visited": [NODE],
        }
    model = conf.model or model_for(NODE)
    assert model is not None  # routed per §3; None would be a routing-table bug

    previous = state.get("aesthetic_qc") or {}
    attempt = int(previous.get("attempts") or 0) + 1
    spec = state.get("design_spec") or {}
    brief = state.get("brief") or {}
    prompt = rubric.build_qc_prompt(
        design_subject=spec.get("brief_subject") or brief.get("subject") or "",
        style=spec.get("style") or "",
        attempt=attempt,
        previous_feedback=previous.get("feedback") or "",
    )
    result = client.vision(
        model=model, prompt=prompt, image_url=image_ref(render["file_url"]), **conf.params
    )
    try:
        scores = rubric.parse_scores(parse_json_object(result.content))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"aesthetic_qc: vision model returned unusable scores: {exc}") from None
    evaluation = rubric.evaluate(scores)

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

    verdict: dict[str, Any] = {
        "result": evaluation["result"],
        "scores": evaluation["scores"],
        "failing": evaluation["failing"],
        "attempts": attempt,
        "model_used": model,
        "rubric_version": rubric.RUBRIC_VERSION,
    }
    output: dict[str, Any] = {"visited": [NODE]}
    if evaluation["result"] == "pass":
        output["aesthetic_qc"] = verdict
    elif attempt <= rubric.MAX_REGEN_RETRIES:
        feedback = rubric.rejection_feedback(evaluation, attempt)
        verdict["feedback"] = feedback
        output["aesthetic_qc"] = verdict
        output["render_feedback"] = feedback
    else:
        verdict["result"] = "fail-human-review"
        output["aesthetic_qc"] = verdict
        if not cfg.get("hitl", {}).get(NODE, DEFAULT_HITL[NODE]):
            errors.append(
                f"{NODE}: retries exhausted with HITL off - proceeding without human review"
            )
        else:
            output["render_feedback"] = ""  # no further regen; human owns it
            interrupt(
                {
                    "node": NODE,
                    "status": "awaiting_human_review",
                    "scores": evaluation["scores"],
                    "failing": evaluation["failing"],
                    "attempts": attempt,
                }
            )
    if errors:
        output["errors"] = errors
    return output


register_node(NODE, aesthetic_qc)
