"""A4 offline parity harness (PBI-015).

Runs brief samples through the full graph with mocked model + Fourthwall
layers and asserts OUTPUT SHAPES (clustered brief set → contract shape,
brief → design-spec shape, render ref, QC scores, placement, price) — shape
and consistency, never pixel or prose equality. The publish step stays uncut:
no PUBLIC product may appear anywhere (asserted).

Offline by default (fully deterministic, no network/DB). ``--live`` uses a
real OpenRouter key + DATABASE_URL cost engine with the FW layer still mocked
(no FW credentials exist in this phase); live misuse exits 2.

Runner note (PBI-015 resolution): the PBI text says ``node
scripts/parity_harness.py`` — Node cannot execute a ``.py`` file. The harness
is Python and runs as ``python scripts/parity_harness.py`` (exit 0 offline);
it is wired into ``npm run verify`` as ``verify:parity``. No JS wrapper was
added (unlisted file = scope creep).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import struct
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # `import pipeline` when run as a script

import httpx
from langgraph.checkpoint.memory import MemorySaver

from pipeline.graph import build_graph
from pipeline.llm import OpenRouterClient
from pipeline.nodes.contract import validate_contract
from pipeline.nodes.shelf import PRICE_INVARIANTS
from pipeline.routing import NODE_ORDER
from pipeline.rubric import CRITERIA

PASS_SCORES = {c: 80 for c in CRITERIA}

GOOD_COPY = {
    "slogan": "Ship It Live",
    "title": "Vibe Coding Tee",
    "description": "A dry joke for developers who review diffs.",
    "tags": ["vibe-coding", "developer-tee"],
}


def _png_bytes(width: int = 256, height: int = 256) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + ihdr
        + b"\x00" * 4
        + b"\x00\x00\x00\x00IEND"
    )


def _prompt_text(body: dict[str, Any]) -> str:
    content = body["messages"][0]["content"]
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content


def mock_transport() -> httpx.MockTransport:
    """Deterministic offline model layer: fixed shapes, valid PNG."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/generations"):
            payload = base64.b64encode(_png_bytes()).decode()
            return httpx.Response(200, json={"data": [{"b64_json": payload}], "usage": {}})
        prompt = _prompt_text(json.loads(request.content))
        if "thematic clusters" in prompt:
            brief_ids = ["b1", "b2"]
            reply: Any = {"clusters": [{"theme": "Vibe Coding", "brief_ids": brief_ids}]}
        elif "listing copy" in prompt:
            reply = GOOD_COPY
        elif "rubric" in prompt:
            reply = dict(PASS_SCORES)
        else:
            reply = {"rcao": "r", "render_prompt": "a monochrome terminal"}
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(reply)}}], "usage": {}}
        )

    return httpx.MockTransport(handler)


class MockFW:
    """Mocked Fourthwall layer: captures the draft, always answers DRAFT."""

    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(payload)
        return {"id": "fw-parity", "state": "DRAFT"}


class MemoryCostEngine:
    """Offline cost sink (mirrors record_cost success without a DB)."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    @contextmanager
    def begin(self):
        engine = self

        class _Conn:
            def execute(self, stmt):
                engine.rows.append(dict(stmt.compile().params))

        yield _Conn()


def check_parity(state: dict[str, Any]) -> list[str]:
    """Shape/consistency assertions. Returns error strings (empty = parity)."""
    errors: list[str] = []

    clusters = state.get("clusters") or []
    if not clusters or not all(c.get("theme") and c.get("brief_ids") for c in clusters):
        errors.append("clusters: expected non-empty candidates with theme + brief_ids")

    contract = state.get("collection_contract") or {}
    shape_errors = validate_contract(contract)
    if shape_errors:
        errors.append(f"contract shape: {shape_errors!r}")

    spec = state.get("design_spec") or {}
    if not spec.get("render_prompt"):
        errors.append("design_spec: missing render_prompt")
    if contract and spec.get("style") != contract.get("style_archetype"):
        errors.append("design_spec: style not inherited from contract")
    if contract and spec.get("palette") != (contract.get("illustration_rules") or {}).get("palette"):
        errors.append("design_spec: palette not inherited from contract")

    render = state.get("render_result") or {}
    ref = render.get("file_url", "")
    if not ref or not Path(ref).exists():
        errors.append("render: artifact reference missing from workspace")
    elif Path(ref).read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        errors.append("render: artifact is not a PNG")

    qc = state.get("aesthetic_qc") or {}
    scores = qc.get("scores") or {}
    if [k for k in CRITERIA if k not in scores]:
        errors.append("aesthetic_qc: scores missing rubric criteria")
    if qc.get("result") not in ("pass", "fail", "fail-human-review"):
        errors.append("aesthetic_qc: unknown result")

    # Draft-stage expectation (documented): CEO has not filled placement
    # templates yet, so placement is honestly unresolved — recorded, not faked.
    placement = state.get("placement") or {}
    placement_errors = [e for e in (state.get("errors") or []) if "placement" in e]
    if placement:
        if sorted(placement) != ["back", "front", "sleeve"]:
            errors.append("placement: zones shape wrong")
    elif not placement_errors:
        errors.append("placement: unresolved but no gap recorded")

    product = state.get("fw_product") or {}
    expected_price = PRICE_INVARIANTS.get(product.get("product_type", ""))
    if product.get("price") != expected_price:
        errors.append("shelf: price does not match the invariant table")
    if not state.get("shelf_result"):
        errors.append("shelf: missing shelf_result")

    decision = state.get("publish_decision") or {}
    if decision.get("state") != "DRAFT":
        errors.append("publish gate: product left DRAFT state")
    if "PUBLIC" in json.dumps(state, default=str):
        errors.append("PARITY VIOLATION: PUBLIC appears in run state (publish uncut)")
    return errors


def run_sample(
    sample: dict[str, Any],
    *,
    llm_client: Any,
    fw_client: Any,
    cost_engine: Any,
    run_dir: str,
    thread_id: str = "parity",
) -> dict[str, Any]:
    """Execute one fixture end-to-end (flags off) and return final state."""
    graph = build_graph(checkpointer=MemorySaver())
    return graph.invoke(
        {
            "design_id": sample.get("design_id", "parity"),
            "collection_id": sample.get("collection_id", ""),
            "brief": sample["brief"],
            "briefs": sample["briefs"],
        },
        {
            "configurable": {
                "thread_id": thread_id,
                "hitl": {n: False for n in NODE_ORDER},
                "llm_client": llm_client,
                "cost_engine": cost_engine,
                "run_dir": run_dir,
                "design_type": sample.get("design_type", "hero-icon"),
                "fw_client": fw_client,
                "fw_live": True,
            }
        },
    )


def load_fixture(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A4 offline parity harness")
    parser.add_argument("--fixture", default=str(REPO_ROOT / "pipeline/tests/fixtures/briefs_sample_a.json"))
    parser.add_argument("--live", action="store_true", help="real OpenRouter key + DB cost engine (FW still mocked)")
    args = parser.parse_args(argv)

    sample = load_fixture(args.fixture)
    if args.live:
        if not os.environ.get("OPENROUTER_API_KEY") or not os.environ.get("DATABASE_URL"):
            print("live mode needs OPENROUTER_API_KEY + DATABASE_URL", file=sys.stderr)
            return 2
        from sqlalchemy import create_engine

        llm_client = OpenRouterClient()
        cost_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
        run_dir = str(REPO_ROOT / "runs" / "parity-live")
    else:
        llm_client = OpenRouterClient(api_key="parity-offline", transport=mock_transport())
        cost_engine = MemoryCostEngine()
        run_dir = tempfile.mkdtemp(prefix="parity-")

    state = run_sample(
        sample,
        llm_client=llm_client,
        fw_client=MockFW(),
        cost_engine=cost_engine,
        run_dir=run_dir,
    )
    errors = check_parity(state)
    report = {
        "sample": sample.get("name", args.fixture),
        "passed": not errors,
        "errors": errors,
        "visited": state.get("visited", []),
        "cost_rows_written": len(getattr(cost_engine, "rows", [])) or "db",
        "render_artifact": (state.get("render_result") or {}).get("file_url"),
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
