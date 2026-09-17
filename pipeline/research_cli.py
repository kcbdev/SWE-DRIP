"""One-shot research runner for ops verification (PBI-058).

Runs a real collection-research graph where the models, database, and
volumes live — typically a production one-shot scheduled task::

    python -m pipeline.research_cli live-review --demo

``--demo`` seeds a clearly-named ``live-review`` draft (validated store
write, refuses overwrite) so a bare volume has something to research.
Without it the slug must already exist with curated inspiration.

Design notes:

- The thread id carries ``RESEARCH_RUN_PREFIX`` so the run shows up in
  ``/api/research/runs`` like any UI-triggered run.
- HITL stays at research defaults (gate ON): a live run pauses for the
  founder's UI approval instead of auto-deciding anything.
- Nothing here runs unattended — no scheduler, no endpoint, no cron
  cadence. Monthly runs stay explicitly started.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pipeline.collection_graph import (
    RESEARCH_DEFAULT_HITL,
    RESEARCH_RUN_PREFIX,
    build_collection_graph,
)

DEMO_SLUG = "live-review"


def _stores():
    """Prod stores on the env-driven roots (PBI-053)."""
    from api.app.collections_store import get_collections_store
    from api.app.inspiration import InspirationStore

    store = get_collections_store()
    return store, InspirationStore()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_demo(store) -> dict[str, Any]:
    """Create the ``live-review`` draft (runnable demo shape: thresholds
    filled plus one ``hero-icon`` placement template, since placement
    refuses to infer either). Refuses when it already exists."""
    record = store.create({
        "collection_id": DEMO_SLUG,
        "theme": "Live Review",
        "status": "draft",
        "style_archetype": "mono-log",
        "illustration_rules": {"line_weight": "thin", "palette": ["#0D0D0D"],
                               "no_mixed_styles": True},
        "garment_colorways": [],
        "placement_templates": [{"design_type": "hero-icon", "front": "chest",
                                 "back": "none", "sleeve": "small-mark"}],
        "product_count_target": 6,
        "lifecycle_days": 90,
        "kpi_thresholds": {"min_units": 5, "min_conversion": 0.02,
                           "eval_window_days": 30},
        "created_by": "ops-cli",
        "created_at": _utcnow(),
        "approved_at": None,
        "retired_at": None,
        "survivor_products": [],
        "inspiration_refs": [{"url": "https://example.com/ops-seed",
                              "note": "ops verification ref"}],
    })
    return record["contract"]


def run_once(*, slug: str, llm_client: Any, cost_engine: Any,
             run_logger: Any, saver: Any, assets_dir: Optional[str] = None,
             thread_id: Optional[str] = None) -> dict[str, Any]:
    """Build inputs from the stores and invoke the research graph once.

    Returns a JSON-serializable summary (also printed by ``main``).
    """
    from api.app.research_runs import build_research_state

    store, inspiration = _stores()
    state = build_research_state(store, inspiration, slug)
    run_id = thread_id or (RESEARCH_RUN_PREFIX + "cli-" + uuid.uuid4().hex[:12])
    hitl = dict(RESEARCH_DEFAULT_HITL)
    if assets_dir is None:
        from pipeline.paths import collections_root

        assets_dir = str(collections_root() / f"{slug}.assets")
    config = {"configurable": {
        "thread_id": run_id,
        "hitl": hitl,
        "llm_client": llm_client,
        "cost_engine": cost_engine,
        "run_logger": run_logger,
        "research_assets_dir": assets_dir,
    }}
    state["hitl"] = hitl
    graph = build_collection_graph(checkpointer=saver)
    graph.invoke(state, config)
    snapshot = graph.get_state({"configurable": {"thread_id": run_id}})
    values = dict(snapshot.values or {})
    interrupted = any(getattr(task, "interrupts", None) for task in (snapshot.tasks or []))
    board = values.get("board") or {}
    draft = values.get("draft_contract") or {}
    return {
        "run_id": run_id,
        "interrupted": interrupted,
        "awaiting_approval": interrupted,
        "board": {"file_ref": board.get("file_ref"),
                  "board_version": board.get("board_version"),
                  "width": board.get("width"), "height": board.get("height")},
        "draft_collection_id": draft.get("collection_id"),
        "diversity_flags": values.get("diversity_flags") or [],
        "gate_decision": values.get("gate_decision"),
        "visited": values.get("visited") or [],
        "errors": values.get("errors") or [],
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry: ``research_cli SLUG [--demo]``. 0 ok, 2 usage/data error."""
    args = list(sys.argv[1:] if argv is None else argv)
    demo = "--demo" in args
    args = [a for a in args if a != "--demo"]
    if len(args) != 1 or not args[0].strip():
        print("usage: python -m pipeline.research_cli SLUG [--demo]", file=sys.stderr)
        return 2
    slug = args[0].strip()
    try:
        from api.app.collections_store import CollectionNotFound
        from api.app.db import get_engine
        from api.app.hitl import _default_saver_factory, _saver_session
        from api.app.research_runs import build_research_state
        from pipeline.llm import OpenRouterClient
        from pipeline.runlog import SqlRunLogger

        store, inspiration = _stores()
        if demo:
            try:
                seed_demo(store)
            except Exception as exc:
                # CollectionExists (and friends) are already loud ValueErrors.
                print(f"demo seed refused: {exc}", file=sys.stderr)
                return 2
        try:
            # Validate slug + curation BEFORE touching engines/keys: a typo
            # exits 2 here instead of building billable clients first.
            build_research_state(store, inspiration, slug)
        except CollectionNotFound:
            print(f"unknown collection {slug!r} — curate it (or --demo) first",
                  file=sys.stderr)
            return 2
        except ValueError as exc:
            print(f"research run refused: {exc}", file=sys.stderr)
            return 2
        engine = get_engine()
        run_id = RESEARCH_RUN_PREFIX + "cli-" + uuid.uuid4().hex[:12]
        logger = SqlRunLogger(engine, run_id)
        with _saver_session(_default_saver_factory) as saver:
            summary = run_once(
                slug=slug,
                llm_client=OpenRouterClient(),
                cost_engine=engine,
                run_logger=logger,
                saver=saver,
                thread_id=run_id,
            )
    except CollectionNotFound:
        print(f"unknown collection {slug!r} — curate it (or --demo) first", file=sys.stderr)
        return 2
    except (ValueError, RuntimeError) as exc:
        print(f"research run refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
