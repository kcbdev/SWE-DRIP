"""One-shot item-run trigger for ops verification (PBI-060).

Starts a real item pipeline run where the models, database, and volumes
live — typically a production one-shot scheduled task::

    python -m pipeline.run_cli live-review --demo

Delegates to ``CheckpointerRunStarter`` — the exact starter behind
``POST /api/runs`` — so brief validation, cost-guard read, frozen HITL,
run logging, and the ``fw_live`` phase lock behave identically. Polls the
checkpointer to paused/terminal and prints a JSON summary.

``--demo`` uses one embedded terminal-themed brief (scores inside the
locked ranges) and ensures the ``live-review`` demo seed carries a
``hero-icon`` placement template (placement refuses to infer one).
Demo-only: real drafts are never touched.

Nothing here runs unattended — explicit invocation only. Gates pause for
the founder in UI exactly like API-started runs.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Optional

from pipeline.nodes.contract import DESIGN_TYPES

from .research_cli import DEMO_SLUG

DEMO_BRIEFS = [{
    "id": "live-1",
    "subject": "Terminal pulse: monochrome line-art tee",
    "engagement": 32,
    "novelty": 24,
    "specificity": 26,
}]

DEMO_TEMPLATE = {"design_type": "hero-icon", "front": "chest",
                 "back": "none", "sleeve": "small-mark"}

POLL_INTERVAL_SECONDS = 5.0
POLL_DEADLINE_SECONDS = 240.0


def ensure_demo_template(store, design_type: str = "hero-icon") -> bool:
    """Add a placement template to the DEMO candidate when missing.

    Scoped to the demo slug only — real collections are never touched.
    Returns True when a write happened.
    """
    record = store.get(DEMO_SLUG)  # raises CollectionNotFound
    templates = list(record["contract"].get("placement_templates") or [])
    if any(isinstance(t, dict) and t.get("design_type") == design_type
           for t in templates):
        return False
    template = dict(DEMO_TEMPLATE)
    template["design_type"] = design_type
    store.update(DEMO_SLUG, {"placement_templates": [*templates, template]})
    return True


def poll_summary(ports, run_id: str, deadline: float = POLL_DEADLINE_SECONDS) -> dict[str, Any]:
    """Newest-state summary, waiting for paused/terminal (pure assembly)."""
    from api.app.runs import derive_status

    end = time.time() + deadline
    history: list = []
    while time.time() < end:
        history = ports.history(run_id)
        if not history:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        values = history[0].values
        if history[0].interrupted or values.get("errors") or _is_complete(values):
            break
        time.sleep(POLL_INTERVAL_SECONDS)
    if not history:
        return {"run_id": run_id, "status": "unknown",
                "note": "no checkpointer history yet"}
    values = history[0].values
    visited = values.get("visited") or []
    return {
        "run_id": run_id,
        "status": derive_status(values, history[0].interrupted),
        "current_node": visited[-1] if visited else None,
        "design_id": values.get("design_id"),
        "collection_id": values.get("collection_id"),
        "errors": values.get("errors") or [],
    }


def _is_complete(values: dict[str, Any]) -> bool:
    from pipeline.routing import NODE_ORDER

    visited = values.get("visited") or []
    return bool(visited) and all(n in visited for n in NODE_ORDER)


def parse_briefs(raw: Optional[str], demo: bool) -> list[dict[str, Any]] | None:
    """Briefs from --briefs JSON, else the embedded demo set with --demo."""
    if raw is not None:
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            raise ValueError(f"--briefs must be a JSON list: {exc}") from None
        if not isinstance(parsed, list):
            raise ValueError("--briefs must be a JSON list of brief objects")
        return parsed
    if demo:
        return [dict(b) for b in DEMO_BRIEFS]
    return None


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry. 0 ok (run polled), 1 run failed, 2 usage/validation/refusal."""
    args = list(sys.argv[1:] if argv is None else argv)
    demo = "--demo" in args
    args = [a for a in args if a != "--demo"]
    design_type: Optional[str] = None
    briefs_raw: Optional[str] = None
    positional: list[str] = []
    index = 0
    while index < len(args):
        if args[index] == "--design-type" and index + 1 < len(args):
            design_type = args[index + 1]
            index += 2
        elif args[index] == "--briefs" and index + 1 < len(args):
            briefs_raw = args[index + 1]
            index += 2
        else:
            positional.append(args[index])
            index += 1
    if len(positional) != 1 or not positional[0].strip():
        print("usage: python -m pipeline.run_cli COLLECTION [--demo] "
              "[--design-type X] [--briefs JSON]", file=sys.stderr)
        return 2
    slug = positional[0].strip()
    if design_type is None and demo:
        design_type = "hero-icon"
    if design_type is not None and design_type not in DESIGN_TYPES:
        print(f"--design-type must be one of {', '.join(sorted(DESIGN_TYPES))}"
              f" — got {design_type!r}", file=sys.stderr)
        return 2
    try:
        briefs = parse_briefs(briefs_raw, demo)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if briefs is not None:
        from api.app.runs import validate_briefs

        problems = validate_briefs(briefs)
        if problems:
            print("briefs invalid:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 2
    try:
        from api.app.agents import GLOBAL_MONTHLY_CAP
        from api.app.db import get_engine
        from api.app.hitl import _default_saver_factory
        from api.app.runs import (
            CheckpointerRunPorts,
            CheckpointerRunStarter,
            SpendUnavailable,
            SqlSpendReader,
        )

        from .research_cli import seed_demo

        engine = get_engine()
        try:
            spent = SqlSpendReader().month_to_date_usd()
        except SpendUnavailable as exc:
            print(f"cannot verify the monthly budget before starting: {exc}",
                  file=sys.stderr)
            return 2
        if spent >= GLOBAL_MONTHLY_CAP:
            print(f"monthly budget cap reached (${spent:.2f} of "
                  f"${GLOBAL_MONTHLY_CAP:.2f}) — refusing", file=sys.stderr)
            return 2
        if demo:
            from api.app.collections_store import CollectionNotFound
            from api.app.collections_store import get_collections_store

            store = get_collections_store()
            try:
                seed_demo(store)
                print(f"demo draft {DEMO_SLUG!r} seeded", file=sys.stderr)
            except ValueError as exc:
                # Already exists (or invalid) — ensure runnable shape instead.
                print(f"demo seed skipped: {exc}", file=sys.stderr)
            try:
                if ensure_demo_template(store, design_type or "hero-icon"):
                    print("demo template ensured", file=sys.stderr)
            except CollectionNotFound:
                print(f"demo draft {DEMO_SLUG!r} missing and seed refused",
                      file=sys.stderr)
                return 2
        saver_factory = _default_saver_factory
        starter = CheckpointerRunStarter(saver_factory=saver_factory)
        started = starter.start(
            collection_id=slug,
            design_id=None,
            briefs=briefs,
            design_type=design_type,
        )
        ports = CheckpointerRunPorts(saver_factory=saver_factory)
        summary = poll_summary(ports, started["run_id"])
    except (ValueError, RuntimeError) as exc:
        print(f"run refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
