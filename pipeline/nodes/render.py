"""Node 5 — art render (spec C2/C3/C4).

Image generation through the routing table: primary first, then the §3
fallbacks in order. Output is validated BEFORE any state write: PNG magic
bytes required, dimensions parsed from IHDR (stdlib ``struct`` — no imaging
dependency). A non-PNG payload is loud; total model failure is loud (the run
fails instead of propagating an empty render into QC/publish).

The artifact bytes land in the run workspace (gitignored ``runs/``); only the
reference enters state. Format/dimension JUDGMENT belongs to technical QC
(PBI-013) — this node records actuals. Per the PBI-012 refinement rule, real
model format surprises (e.g. missing alpha) are recorded as findings, never
patched around here.
"""

from __future__ import annotations

import base64
import struct
from pathlib import Path
from typing import Any

import httpx
from langgraph.types import RunnableConfig, interrupt

from ..costs import build_cost_record, record_cost
from ..graph import DEFAULT_HITL, register_node
from ..routing import IMAGE_FALLBACKS, model_for
from ..state import RunState

NODE = "art_render"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_png_dimensions(data: bytes) -> tuple[int, int]:
    """Validate PNG magic + return (width, height) from IHDR. Loud on garbage."""
    if data[:8] != PNG_SIGNATURE:
        raise ValueError("render output is not a PNG (bad magic bytes)")
    if len(data) < 24:
        raise ValueError("render output is a truncated PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _payload_bytes(content: Any) -> bytes:
    if isinstance(content, bytes):
        return content
    if isinstance(content, str) and content.startswith(("http://", "https://")):
        response = httpx.get(content, timeout=120.0)
        response.raise_for_status()
        return response.content
    if isinstance(content, str):
        try:
            return base64.b64decode(content, validate=True)
        except Exception as exc:
            raise ValueError(f"render output is not base64 image data: {exc}") from None
    raise ValueError(f"render output has no usable image payload: {type(content)}")


def art_render(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Node 5 implementation: primary → fallbacks → validate → persist ref."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})

    spec = state.get("design_spec")
    if not spec or not spec.get("render_prompt"):
        return {
            "render_result": {},
            "visited": [NODE],
            "errors": [f"{NODE}: no design spec with render_prompt in state"],
        }
    client = cfg.get("llm_client")
    if client is None:
        raise RuntimeError(
            "art_render: no llm_client in config['configurable'] "
            "(the production runner injects OpenRouterClient)"
        )
    primary = model_for(NODE)
    assert primary is not None  # routed per §3; None would be a routing-table bug
    models = [primary, *IMAGE_FALLBACKS]

    result = None
    used_model = None
    failures: list[str] = []
    for candidate in models:
        try:
            result = client.image(model=candidate, prompt=spec["render_prompt"])
            used_model = candidate
            break
        except Exception as exc:  # try next model; all failing is loud below
            failures.append(f"{candidate}: {type(exc).__name__}: {exc}")
    if result is None or used_model is None:
        raise RuntimeError(f"art_render: all image models failed: {failures!r}")

    image_bytes = _payload_bytes(result.content)
    width, height = parse_png_dimensions(image_bytes)  # validated before state write

    design_id = state.get("design_id") or "adhoc"
    run_dir = Path(cfg.get("run_dir") or f"runs/{design_id}")
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact = run_dir / "render.png"
    artifact.write_bytes(image_bytes)

    render_ref = {
        "file_url": str(artifact),
        "model_used": used_model,
        "width": width,
        "height": height,
        "colorways_valid": [],  # filled by placement/colorway resolution (PBI-013)
    }

    errors: list[str] = []
    usage = result.raw.get("usage") or {}
    record = build_cost_record(
        NODE,
        used_model,
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

    output: dict[str, Any] = {
        "render_result": render_ref,
        "render": {
            "file_url": str(artifact),
            "model_used": used_model,
            "colorways_valid": [],
        },
        "visited": [NODE],
    }
    if errors:
        output["errors"] = errors
    return output


register_node(NODE, art_render)
