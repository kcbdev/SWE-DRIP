"""Node 8 — technical QC (spec C9).

Deterministic validation of the render artifact: PNG integrity, alpha-channel
presence (print-on-demand needs transparency), parseable dimensions. Actuals
are recorded; there is no spec'd expected size to judge against (spec gap —
flagged in the PBI-013 resolution), so dimensions are reported, not gated,
beyond being parseable and non-degenerate. No model calls.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..graph import DEFAULT_HITL, register_node
from ..state import RunState

NODE = "technical_qc"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ALPHA_COLOR_TYPES = (4, 6)  # grayscale+alpha, truecolor+alpha


def inspect_png(data: bytes) -> dict[str, Any]:
    """Parse PNG header: signature, dimensions, color type, alpha. Loud on garbage."""
    checks: list[str] = []
    if data[:8] != PNG_SIGNATURE:
        return {"passed": False, "checks": ["not a PNG (bad magic bytes)"]}
    checks.append("png magic ok")
    if len(data) < 26:
        return {"passed": False, "checks": checks + ["truncated PNG (no IHDR)"]}
    width, height = struct.unpack(">II", data[16:24])
    color_type = data[25]
    checks.append(f"dimensions {width}x{height}")
    if width < 1 or height < 1:
        return {"passed": False, "width": width, "height": height,
                "color_type": color_type, "has_alpha": False, "checks": checks + ["degenerate dimensions"]}
    has_alpha = color_type in ALPHA_COLOR_TYPES
    checks.append(f"color type {color_type} ({'alpha' if has_alpha else 'no alpha'})")
    if not has_alpha:
        return {"passed": False, "width": width, "height": height,
                "color_type": color_type, "has_alpha": False,
                "checks": checks + ["missing alpha channel (transparency required)"]}
    return {"passed": True, "width": width, "height": height,
            "color_type": color_type, "has_alpha": True,
            "checks": checks + ["alpha channel present"]}


def technical_qc(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Node 8 implementation: inspect artifact bytes, record verdict."""
    cfg = (config or {}).get("configurable") or {}
    if cfg.get("hitl", {}).get(NODE, DEFAULT_HITL[NODE]):
        interrupt({"node": NODE, "status": "awaiting_approval"})

    render = state.get("render_result") or {}
    if not render or not render.get("file_url"):
        return {
            "technical_qc": {"passed": False, "reason": "no render"},
            "visited": [NODE],
            "errors": [f"{NODE}: no render artifact in state"],
        }
    try:
        data = Path(render["file_url"]).read_bytes()
    except OSError as exc:
        return {
            "technical_qc": {"passed": False, "reason": "unreadable artifact"},
            "visited": [NODE],
            "errors": [f"{NODE}: cannot read render artifact: {exc}"],
        }
    verdict = inspect_png(data)
    return {"technical_qc": verdict, "visited": [NODE]}


register_node(NODE, technical_qc)
