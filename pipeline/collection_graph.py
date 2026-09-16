"""Collection-research graph (spec C4, PBI-050) — the monthly creative layer.

Locked node order: ``inspiration_review → style_synthesis → mood_board →
contract_draft → collection_gate``. Monthly cadence is operational (run on
demand from the research UI / PBI-052); no scheduler lives here.

This graph PRODUCES locked contracts; it never writes ``active`` — drafts
enter the existing collections lifecycle (candidates → approve → active).
It reuses the item graph's transverse patterns (runlog, costs) but keeps
its own state, registry, and assembly: research inputs (inspiration,
lineage) and monthly rhythm differ structurally from daily item runs, and
merging the two would tangle both orderings.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Callable

from langgraph.graph import END, START, StateGraph
from langgraph.types import RunnableConfig
from typing_extensions import TypedDict

RESEARCH_ORDER: list[str] = [
    "inspiration_review",  # inventory + validate the curated input
    "style_synthesis",  # locked directives via the routed model
    "mood_board",  # board sheet render (style samples, never products)
    "contract_draft",  # v2 contract assembly (empty where unknowable)
    "collection_gate",  # CEO approve / edit-and-approve / reject (HITL on)
]

# Research gates default ON — a creative decision without review is the
# failure mode this graph exists to prevent (unlike item nodes, where most
# gates default off for throughput).
RESEARCH_DEFAULT_HITL: dict[str, bool] = {
    "inspiration_review": False,
    "style_synthesis": False,
    "mood_board": False,
    "contract_draft": False,
    "collection_gate": True,
}


class CollectionResearchState(TypedDict, total=False):
    """Research-run state (declared — no keys smuggled through the graph)."""

    collection_slug: str
    collection_theme: str
    style_archetype: str
    inspiration: dict[str, Any]  # {assets: [...], refs: [...]} as ingested
    avoid: list[str]  # lineage negative context (PBI-051 owns the record)
    synthesis: dict[str, Any]  # locked directives + model/version metadata
    board: dict[str, Any]  # artifact ref + board_version
    draft_contract: dict[str, Any]
    gate_decision: dict[str, Any]
    visited: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]


_RESEARCH_IMPLS: dict[str, Callable[..., dict[str, Any]]] = {}


def register_research_node(name: str, fn: Callable[..., dict[str, Any]]) -> None:
    """Register a research node implementation (called by research_* modules)."""
    if name not in RESEARCH_ORDER:
        raise KeyError(f"cannot register unknown research node: {name!r}")
    _RESEARCH_IMPLS[name] = fn


def _placeholder(name: str) -> Callable[..., dict[str, Any]]:
    def run(state: CollectionResearchState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
        return {"visited": [name]}

    run.__name__ = f"research_{name}"
    return run


def build_collection_graph(checkpointer=None):
    """Assemble and compile the locked research graph."""
    from .nodes import research_board  # noqa: F401
    from .nodes import research_draft  # noqa: F401
    from .nodes import research_gate  # noqa: F401
    from .nodes import research_review  # noqa: F401
    from .nodes import research_synthesis  # noqa: F401

    builder = StateGraph(CollectionResearchState)
    previous = START
    for name in RESEARCH_ORDER:
        builder.add_node(name, _RESEARCH_IMPLS.get(name, _placeholder(name)))
        builder.add_edge(previous, name)
        previous = name
    builder.add_edge(previous, END)
    return builder.compile(checkpointer=checkpointer)
