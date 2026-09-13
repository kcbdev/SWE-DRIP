"""Typed run state for the SWE Drip pipeline (spec C1).

Carries the design record shape from data spec §1.3
(``design_id, collection_id, brief, render, qc_scores, placement``) plus
per-node intermediates. The full state of every run is queryable from the
LangGraph checkpointer — no parallel state copy (PRD NFR-1).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class Brief(TypedDict, total=False):
    subject: str
    text: str
    style: str


class Render(TypedDict, total=False):
    file_url: str
    model_used: str
    colorways_valid: list[str]


class QCScores(TypedDict, total=False):
    style_cohesion: int
    focal_point: int
    placement_fit: int
    contrast: int
    pass_threshold: int
    result: str  # "pass" | "fail"


class Placement(TypedDict, total=False):
    front: str
    back: str
    sleeve: str


class RunState(TypedDict, total=False):
    """LangGraph state — design record (§1.3) + node intermediates."""

    design_id: str
    collection_id: str
    brief: Brief
    render: Render
    qc_scores: QCScores
    placement: Placement
    # Per-node intermediates (populated by nodes 1–11; see graph.py order).
    clusters: list[dict[str, Any]]
    collection_contract: dict[str, Any]
    listing_copy: dict[str, Any]
    design_spec: dict[str, Any]
    render_result: dict[str, Any]
    aesthetic_qc: dict[str, Any]
    technical_qc: dict[str, Any]
    fw_product: dict[str, Any]
    publish_decision: dict[str, Any]
    shelf_result: dict[str, Any]
    # Run bookkeeping (append-only reducers).
    visited: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
