"""Node 2 — collection contract approval (spec C2/C3).

Drafts one candidate contract per cluster, pre-filling every field derivable
from the cluster (collections spec C3: "pre-filled from the cluster's fields;
the CEO may edit before approving"). Fields with no cluster source
(line weight, palette, thresholds, targets) are present with explicit
empty placeholders — never invented values. Then pauses on ``interrupt()``
with the drafts as payload; resume carries the CEO's selection.

``validate_contract`` enforces §1.1 shape + locked enums + the brand-lock
(``no_mixed_styles`` is always true). It deliberately does NOT enum-check
``style_archetype``: the "7 locked brand styles" are named nowhere in the
spec kit (spec gap, flagged in the PBI-011 resolution) — inventing the list
would be fabrication. Value-completeness (filled palette, thresholds) is
enforced at approval time by the collections store (PBI-019/020), not here.

Status stays ``draft`` with ``approved_at`` null through this node; the
atomic activate-stamp is the collections lifecycle's job (PBI-020).
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from langgraph.types import RunnableConfig, interrupt

from ..graph import DEFAULT_HITL, register_node
from ..runlog import get_logger
from ..state import RunState

NODE = "contract_approval"

STATUS_VALUES = ("draft", "active", "retired")
DESIGN_TYPES = ("hero-icon", "wordmark", "log-block", "brand-mark-only")
PLACEMENT_ZONES = ("none", "chest", "full")
# Sleeve accepts small-mark per the §1.3 design-record example
# ({"sleeve": "small-mark"}); front/back are exactly the §1.1 enums.
SLEEVE_ZONES = ("none", "chest", "full", "small-mark")

CONTRACT_KEYS = (
    "collection_id",
    "theme",
    "status",
    "style_archetype",
    "illustration_rules",
    "garment_colorways",
    "placement_templates",
    "product_count_target",
    "lifecycle_days",
    "kpi_thresholds",
    "created_by",
    "created_at",
    "approved_at",
    "retired_at",
    # PBI-020: A9 survivor exception persisted by the collections lifecycle.
    "survivor_products",
)


def slugify(theme: str) -> str:
    """Deterministic slug for ``collection_id`` (uniqueness is the store's job)."""
    slug = re.sub(r"[^a-z0-9]+", "-", theme.lower()).strip("-")
    return slug or "untitled"


def draft_contract(
    cluster: dict[str, Any],
    member_styles: list[str],
    created_by: str = "system",
) -> dict[str, Any]:
    """Build a shape-valid draft from one cluster (pure, deterministic)."""
    for key in ("cluster_id", "theme", "brief_ids"):
        if key not in cluster:
            raise ValueError(f"cluster missing {key!r}: {cluster!r}")
    styles = [s for s in member_styles if s]
    if not styles:
        raise ValueError(
            f"cluster {cluster['cluster_id']!r} has no member styles — "
            "cannot lock style_archetype"
        )
    # Most common wins; ties break alphabetically (deterministic).
    top_count = Counter(styles).most_common()
    style = sorted(s for s, c in top_count if c == top_count[0][1])[0]
    return {
        "collection_id": slugify(str(cluster["theme"])),
        "theme": cluster["theme"],
        "status": "draft",
        "style_archetype": style,
        "illustration_rules": {"line_weight": None, "palette": [], "no_mixed_styles": True},
        "garment_colorways": [],
        "placement_templates": [],
        "product_count_target": None,
        "lifecycle_days": None,
        "kpi_thresholds": {"min_units": None, "min_conversion": None, "eval_window_days": None},
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_at": None,
        "retired_at": None,
        "survivor_products": [],
    }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_contract(contract: dict[str, Any]) -> list[str]:
    """Shape + locked-enum validation against §1.1. Returns error strings."""
    errors: list[str] = []
    if not isinstance(contract, dict):
        return ["contract must be a mapping"]
    unknown = [k for k in contract if k not in CONTRACT_KEYS]
    if unknown:
        errors.append(f"unknown fields: {sorted(unknown)!r}")
    missing = [k for k in CONTRACT_KEYS if k not in contract]
    if missing:
        errors.append(f"missing fields: {missing!r}")
        return errors

    if contract["status"] not in STATUS_VALUES:
        errors.append(f"status must be one of {STATUS_VALUES!r}")
    if not contract.get("style_archetype") or not isinstance(contract["style_archetype"], str):
        errors.append("style_archetype must be a non-empty string")

    rules = contract.get("illustration_rules")
    if not isinstance(rules, dict):
        errors.append("illustration_rules must be a mapping")
    else:
        if rules.get("line_weight") is not None and not isinstance(rules["line_weight"], str):
            errors.append("illustration_rules.line_weight must be a string when set")
        if not isinstance(rules.get("palette"), list):
            errors.append("illustration_rules.palette must be a list")
        if rules.get("no_mixed_styles") is not True:
            errors.append("illustration_rules.no_mixed_styles must be true (brand-lock)")

    colorways = contract.get("garment_colorways")
    if not isinstance(colorways, list):
        errors.append("garment_colorways must be a list")
    else:
        for i, entry in enumerate(colorways):
            if not isinstance(entry, dict) or not entry.get("base"):
                errors.append(f"garment_colorways[{i}] needs a base")
            elif entry.get("contrast_pass") not in (True, False):
                errors.append(f"garment_colorways[{i}].contrast_pass must be boolean")

    templates = contract.get("placement_templates")
    if not isinstance(templates, list):
        errors.append("placement_templates must be a list")
    else:
        for i, entry in enumerate(templates):
            if not isinstance(entry, dict):
                errors.append(f"placement_templates[{i}] must be a mapping")
                continue
            if entry.get("design_type") not in DESIGN_TYPES:
                errors.append(f"placement_templates[{i}].design_type must be one of {DESIGN_TYPES!r}")
            if entry.get("front") not in PLACEMENT_ZONES or entry.get("back") not in PLACEMENT_ZONES:
                errors.append(f"placement_templates[{i}].front/back must be one of {PLACEMENT_ZONES!r}")
            if entry.get("sleeve") not in SLEEVE_ZONES:
                errors.append(f"placement_templates[{i}].sleeve must be one of {SLEEVE_ZONES!r}")

    for key in ("product_count_target", "lifecycle_days"):
        value = contract.get(key)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
            errors.append(f"{key} must be a positive integer when set")

    thresholds = contract.get("kpi_thresholds")
    if not isinstance(thresholds, dict):
        errors.append("kpi_thresholds must be a mapping")
    else:
        for key in ("min_units", "min_conversion", "eval_window_days"):
            value = thresholds.get(key)
            if value is not None and (not _is_number(value) or value < 0):
                errors.append(f"kpi_thresholds.{key} must be a non-negative number when set")

    if not contract.get("created_by") or not isinstance(contract["created_by"], str):
        errors.append("created_by must be a non-empty string")
    if not contract.get("created_at") or not isinstance(contract["created_at"], str):
        errors.append("created_at must be a timestamp string")
    for key in ("approved_at", "retired_at"):
        if contract.get(key) is not None and not isinstance(contract[key], str):
            errors.append(f"{key} must be null or a timestamp string")
    return errors


def _select_cluster_brief(
    cluster: dict[str, Any], briefs_by_id: dict[Any, dict[str, Any]]
) -> dict[str, Any] | None:
    """Pick the design brief that represents ``cluster`` (pure, deterministic).

    Nodes 3-8 all require ``state["brief"]`` and nothing upstream used to set it,
    so a real run failed at ``listing_copy`` with "no design brief in state".
    A cluster holds several briefs; the representative is the highest total score
    (engagement+novelty+specificity), ties broken by brief id for stability —
    no random pick, and reproducible for the same brief set.
    """

    members = [
        briefs_by_id[bid] for bid in cluster.get("brief_ids", []) if bid in briefs_by_id
    ]
    if not members:
        return None
    ordered = sorted(
        members, key=lambda b: (-_total_score(b), str(b.get("id") or ""))
    )
    best = ordered[0]
    return {
        "subject": best.get("subject") or "",
        "text": best.get("text") or "",
        "style": best.get("style") or "",
    }


def _total_score(brief: dict[str, Any]) -> int:
    total = 0
    for field in ("engagement", "novelty", "specificity"):
        value = brief.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total += int(value)
    return total


def contract_approval(state: RunState, config: RunnableConfig = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Node 2 implementation: draft per cluster → interrupt → resume-select.

    Also resolves the cluster's representative design ``brief`` for nodes 3-8
    (see :func:`_select_cluster_brief`) — without it the rest of the graph has
    nothing to design from.
    """
    cfg = (config or {}).get("configurable") or {}
    clusters = state.get("clusters") or []
    log = get_logger(cfg)
    rid = str(cfg.get("thread_id") or "")
    if not clusters:
        log.error(NODE, "no clusters to draft from", run_id=rid)
        return {
            "collection_contract": {},
            "visited": [NODE],
            "errors": [f"{NODE}: no clusters to draft from"],
        }

    briefs_by_id = {b.get("id"): b for b in (state.get("briefs") or [])}

    # An already-approved contract supplied by the run (read from the collection
    # store, spec C3) is used as-is: it carries real placement templates and
    # colorways, and re-drafting would replace them with placeholders. No gate —
    # the contract was approved when the collection was.
    supplied = state.get("collection_contract") or {}
    if supplied:
        log.info(NODE, f"using stored contract {supplied.get('collection_id')!r} as-is",
                 run_id=rid)
        return _with_cluster_brief(supplied, clusters[0], briefs_by_id)

    actor = cfg.get("actor_user_id") or "system"
    drafts = []
    for cluster in clusters:
        styles = [
            briefs_by_id[bid].get("style")
            for bid in cluster.get("brief_ids", [])
            if briefs_by_id.get(bid, {}).get("style")
        ]
        drafts.append(draft_contract(cluster, styles, created_by=actor))
    problems = [e for draft in drafts for e in validate_contract(draft)]
    if problems:  # self-invalid draft is a code bug — loud, never silent
        raise RuntimeError(f"{NODE}: drafted an invalid contract: {problems!r}")

    if cfg.get("hitl", {}).get(NODE, DEFAULT_HITL[NODE]):
        log.info(NODE, f"{len(drafts)} drafts awaiting approval", run_id=rid)
        decision = interrupt({"node": NODE, "status": "awaiting_approval", "contracts": drafts})
        approved_id = decision.get("approved_cluster_id") if isinstance(decision, dict) else None
        chosen = next((d for d, c in zip(drafts, clusters) if c["cluster_id"] == approved_id), None)
        chosen_cluster = next(
            (c for c in clusters if c["cluster_id"] == approved_id), None
        )
        if chosen is None or chosen_cluster is None:
            log.error(NODE, f"resume decision missing or unknown approved_cluster_id ({approved_id!r})",
                      run_id=rid)
            return {
                "collection_contract": {},
                "visited": [NODE],
                "errors": [
                    f"{NODE}: resume decision missing or unknown approved_cluster_id ({approved_id!r})"
                ],
            }
        log.info(NODE, f"approved cluster {approved_id!r}", run_id=rid)
    else:
        # HITL off (tests/parity): first cluster proceeds; candidate
        # selection UX is the collections lifecycle's job (PBI-020).
        chosen = drafts[0]
        chosen_cluster = clusters[0]

    brief = _select_cluster_brief(chosen_cluster, briefs_by_id)
    if brief is None:
        log.error(NODE, f"selected cluster {chosen_cluster.get('cluster_id')!r} has no resolvable member brief",
                  run_id=rid)
        return {
            "collection_contract": chosen,
            "visited": [NODE],
            "errors": [
                f"{NODE}: selected cluster {chosen_cluster.get('cluster_id')!r} has no "
                "resolvable member brief — cannot design from it"
            ],
        }
    log.info(NODE, f"contract {chosen.get('collection_id')!r} selected", run_id=rid)
    return {"collection_contract": chosen, "brief": brief, "visited": [NODE]}


def _with_cluster_brief(
    contract: dict[str, Any],
    cluster: dict[str, Any],
    briefs_by_id: dict[Any, dict[str, Any]],
) -> dict[str, Any]:
    """Pass an approved contract through, still resolving the design brief.

    Nodes 3-8 need ``brief``; the contract alone does not carry one.
    """
    brief = _select_cluster_brief(cluster, briefs_by_id)
    if brief is None:
        return {
            "collection_contract": contract,
            "visited": [NODE],
            "errors": [
                f"{NODE}: collection {contract.get('collection_id')!r} has no resolvable "
                "brief for its cluster — cannot design from it"
            ],
        }
    return {"collection_contract": contract, "brief": brief, "visited": [NODE]}


register_node(NODE, contract_approval)
