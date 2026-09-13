"""StateGraph assembly — the SINGLE assembly point for the pipeline.

Locked 11-node order (Vision doc §3.2) wired linearly: START → 1 → … → 11 → END.
Every node is ``interrupt()``-capable from the start; HITL on/off is a config
flag (``config["configurable"]["hitl"][node]``, defaulting to
:const:`DEFAULT_HITL`), never a structural branch — so toggling a gate is a
config change, never a rebuild.

PBI-010 ships placeholder node bodies (visited-tracking only) so the graph
compiles and runs end-to-end. Node PBIs (011–014) register real implementations
via :func:`register_node`; each extends this file with its edges (e.g. the
aesthetic-QC regen loop lands in PBI-013).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import RunnableConfig, interrupt

from .routing import NODE_ORDER
from .state import RunState

# HITL defaults from Vision doc §3.2 (node 9 has no flag; node 7 stays on
# until calibrated against real pass/fail history — see Vision §5).
DEFAULT_HITL: dict[str, bool] = {
    "trend_research": False,
    "contract_approval": True,
    "listing_copy": False,
    "design_spec": False,
    "art_render": False,
    "placement": False,
    "aesthetic_qc": True,
    "technical_qc": False,
    "fw_create": False,
    "publish_gate": True,
    "shelf": False,
}

# Real implementations registered by node PBIs; absent nodes run placeholders.
_NODE_IMPLS: dict[str, Callable[..., dict[str, Any]]] = {}


def register_node(name: str, fn: Callable[..., dict[str, Any]]) -> None:
    """Register a node's real implementation (called by node PBIs)."""
    if name not in NODE_ORDER:
        raise KeyError(f"cannot register unknown pipeline node: {name!r}")
    _NODE_IMPLS[name] = fn


def _placeholder(name: str) -> Callable[..., dict[str, Any]]:
    def run(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
        flags = ((config or {}).get("configurable") or {}).get("hitl", {})
        if flags.get(name, DEFAULT_HITL.get(name, False)):
            interrupt({"node": name, "status": "awaiting_approval"})
        return {"visited": [name]}

    run.__name__ = f"node_{name}"
    return run


def route_after_aesthetic_qc(state: RunState) -> str:
    """Conditional edge (PBI-013): regen loop back to render, else onward.

    Fail verdict + fresh feedback → ``art_render`` (placement re-runs
    deterministically afterwards at zero model cost). Pass, human-review, or
    fail-without-feedback → ``technical_qc``.
    """
    verdict = state.get("aesthetic_qc") or {}
    if verdict.get("result") == "fail" and state.get("render_feedback"):
        return "art_render"
    return "technical_qc"


def build_graph(checkpointer=None):
    """Assemble and compile the locked 11-node graph."""
    from . import nodes  # noqa: F401 — triggers register_node calls before assembly

    builder = StateGraph(RunState)
    previous = START
    for name in NODE_ORDER:
        builder.add_node(name, _NODE_IMPLS.get(name, _placeholder(name)))
        if previous == "aesthetic_qc":
            builder.add_conditional_edges(
                previous, route_after_aesthetic_qc, ["art_render", "technical_qc"]
            )
        else:
            builder.add_edge(previous, name)
        previous = name
    builder.add_edge(previous, END)
    return builder.compile(checkpointer=checkpointer)
