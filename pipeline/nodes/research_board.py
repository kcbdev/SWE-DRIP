"""Research node 3 — mood-board render (spec C4).

Renders the board sheet via the image model: style samples for the
synthesized directives, never products. The bytes land under the
collection's asset dir (caller-supplied
``config["configurable"]["research_assets_dir"]``, defaulting to the
repo-relative convention); only the reference enters state. PNG-validated
before any state write (render-node pattern). Each render bumps the
contract's board version downstream.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..collection_graph import RESEARCH_DEFAULT_HITL, register_research_node
from ..costs import build_cost_record, record_cost
from ..paths import collections_root
from ..routing import GEMINI_FLASH_IMAGE, IMAGE_FALLBACKS
from ..runlog import get_logger
from .render import _payload_bytes, parse_png_dimensions

NODE = "mood_board"

PRIMARY_MODEL = GEMINI_FLASH_IMAGE


def build_board_prompt(synthesis: dict[str, Any]) -> str:
    """Board-sheet prompt (pure — asserted in tests)."""
    descriptors = synthesis.get("style_descriptors") or []
    motifs = synthesis.get("motifs") or []
    avoid = synthesis.get("avoid") or []
    lines = [
        "Render a style mood-board sheet (NOT a product, NOT a t-shirt mockup): "
        "a grid of small style samples demonstrating these graphic directives. "
        "Reply with a PNG image.",
        f"Directives: {', '.join(str(d) for d in descriptors)}.",
        f"Motifs to sample: {', '.join(str(m) for m in motifs)}.",
    ]
    if avoid:
        lines.append(f"Explicitly avoid: {', '.join(str(a) for a in avoid)}.")
    return "\n".join(lines)


def art_render_board(prompt: str, client: Any, models: list[str]) -> tuple[Any, str]:
    """First working image model wins; all failing is loud."""
    failures: list[str] = []
    for candidate in models:
        try:
            return client.image(model=candidate, prompt=prompt), candidate
        except Exception as exc:
            failures.append(f"{candidate}: {type(exc).__name__}: {exc}")
    raise RuntimeError(f"{NODE}: all image models failed: {failures!r}")


def mood_board(
    state: dict[str, Any], config: RunnableConfig = None  # type: ignore[assignment]
) -> dict[str, Any]:
    """Node 3 implementation: render → validate → persist ref."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, RESEARCH_DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})
    log = get_logger(cfg)
    rid = str(cfg.get("thread_id") or "")
    synthesis = state.get("synthesis")
    if not synthesis or not synthesis.get("style_descriptors"):
        log.error(NODE, "no synthesis with style_descriptors in state", run_id=rid)
        return {
            "visited": [NODE],
            "errors": [f"{NODE}: no synthesis with style_descriptors in state"],
        }
    client = cfg.get("llm_client")
    if client is None:
        raise RuntimeError(f"{NODE}: no llm_client in config['configurable']")
    models = [((cfg.get("research_models") or {}).get(NODE)) or PRIMARY_MODEL,
              *IMAGE_FALLBACKS]
    prompt = build_board_prompt(synthesis)
    log.info(NODE, f"rendering board with {models[0]}", run_id=rid,
             detail={"model": models[0]})
    result, used_model = art_render_board(prompt, client, models)
    try:
        image_bytes = _payload_bytes(result.content)
        width, height = parse_png_dimensions(image_bytes)  # validated before write
    except ValueError as exc:
        log.error(NODE, f"board payload unusable: {exc}", run_id=rid)
        raise ValueError(f"{NODE}: board payload unusable: {exc}") from None

    slug = state.get("collection_slug") or "adhoc"
    assets_dir = Path(cfg.get("research_assets_dir") or (collections_root() / f"{slug}.assets"))
    assets_dir.mkdir(parents=True, exist_ok=True)
    artifact = assets_dir / "board.png"
    suffix = 2
    while artifact.exists():  # re-renders must not overwrite prior boards
        artifact = assets_dir / f"board-r{suffix}.png"
        suffix += 1
    artifact.write_bytes(image_bytes)

    board = {
        "file_ref": str(artifact),
        "model_used": used_model,
        "width": width,
        "height": height,
        "board_version": int((state.get("board") or {}).get("board_version") or 0) + 1,
    }
    errors: list[str] = []
    usage = result.raw.get("usage") or {}
    record = build_cost_record(
        NODE, used_model,
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
    output: dict[str, Any] = {"board": board, "visited": [NODE]}
    if errors:
        output["errors"] = errors
    log.info(NODE, f"board {width}x{height} via {used_model}", run_id=rid)
    return output


register_research_node(NODE, mood_board)
