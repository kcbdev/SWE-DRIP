"""Read-only graph inspection (operator-mcp C4).

Reports the locked pipeline structure — order, edges, per-node state keys,
and where each node's runtime config resolves from. No parameters mutate;
no tool here can add, remove, reorder, or rewire nodes (locked Vision §3.2
invariant — structural change stays a code + spec-amendment path).

Edges are derived from ``NODE_ORDER`` adjacency plus the single conditional
edge (``route_after_aesthetic_qc``); a test pins this against the order so
the report cannot drift from the graph.
"""

from __future__ import annotations

from typing import Any

from pipeline.routing import MODEL_FOR_NODE, NODE_ORDER

from ..runs import NODE_STATE_KEY
from .auth import SCOPE_READ, require_scope


def graph_edges() -> dict[str, Any]:
    """Locked edges: linear chain plus the QC regen conditional (pure)."""
    linear = [{"from": a, "to": b} for a, b in zip(NODE_ORDER, NODE_ORDER[1:])]
    return {
        "linear": linear,
        "conditional": {
            "aesthetic_qc": ["art_render", "technical_qc"],
            "rule": "route_after_aesthetic_qc: fail verdict + fresh render_feedback "
                    "→ art_render (regen); else technical_qc",
        },
    }


def node_config_source(node: str) -> dict[str, Any]:
    """Where one node's runtime config resolves from (live override presence)."""
    from pipeline.prompts import PROMPT_KEYS

    from ..settings_store import get_node_config_override

    try:
        raw = get_node_config_override(node)
        overridden = sorted(k for k, v in raw.items() if v is not None)
    except Exception:
        overridden = []
    return {
        "model_default": MODEL_FOR_NODE.get(node),
        "model_source": "pipeline/routing.py defaults < settings store node_config override",
        "store_overridden": overridden,
        "prompt_key": PROMPT_KEYS.get(node),
        "params_default": {},
        "enabled_default": True,
    }


async def graph_inspect() -> dict[str, Any]:
    """Locked graph structure: order, edges, state keys, config sources."""
    require_scope(SCOPE_READ)
    assert set(NODE_STATE_KEY) == set(NODE_ORDER)  # tracker can never drift
    return {
        "node_order": list(NODE_ORDER),
        "edges": graph_edges(),
        "nodes": {
            node: {"state_key": NODE_STATE_KEY[node], **node_config_source(node)}
            for node in NODE_ORDER
        },
    }
