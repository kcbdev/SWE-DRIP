"""Fourthwall product-create spike — SUPERSEDED (see ADR-004, Accepted 2026-09-15).

STATUS: NOT EVIDENCE. ADR-004 decided the v1 product-create mechanism is the
hand-rolled Platform Open API flow. This harness exercised the MCP write tool,
which v1 does not use, and its ``CREATE_TOOL_CANDIDATES`` match no real MCP tool
(the real ones are ``ecommerce_create-digital-offer``,
``ecommerce_create-offers-from-designs``, ``ecommerce_update-offer``), so a
``--live`` run today would report a false negative.

Kept for history only. The ``--dry-run`` shape test still runs in CI.

If an MCP write path is ever revisited, it first needs an OAuth connect flow
(ADR-005), then a harness pointed at the real tool names above.

Usage (historical):
    python scripts/fw_create_spike.py --dry-run        # offline shape test (mocked), exit 0
    python scripts/fw_create_spike.py --live            # real MCP session (needs env + founder)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Placement matrix under test: every (design_type × front × back × sleeve ×
# colorway) shape the pipeline's FW-create node may emit (data spec §1.1).
MATRIX: list[dict[str, Any]] = [
    {"design_type": "hero-icon", "front": "chest", "back": "none", "sleeve": "none",
     "colorways": ["black"]},
    {"design_type": "wordmark", "front": "full", "back": "none", "sleeve": "none",
     "colorways": ["black", "charcoal"]},
    {"design_type": "log-block", "front": "none", "back": "full", "sleeve": "none",
     "colorways": ["white"]},
    {"design_type": "hero-icon", "front": "chest", "back": "none", "sleeve": "small-mark",
     "colorways": ["black"]},
    {"design_type": "brand-mark-only", "front": "none", "back": "none", "sleeve": "small-mark",
     "colorways": ["charcoal"]},
]

CREATE_TOOL_CANDIDATES = ("create_product", "products_create", "create_draft_product")


def build_draft_payload(case: dict[str, Any]) -> dict[str, Any]:
    """DRAFT-only payload for one matrix case (prices from shelf invariants)."""
    return {
        "title": f"SPIKE {case['design_type']} {case['front']}/{case['back']}/{case['sleeve']}",
        "state": "DRAFT",
        "placement": {
            "design_type": case["design_type"],
            "front": case["front"],
            "back": case["back"],
            "sleeve": case["sleeve"],
        },
        "colorways": case["colorways"],
        "price_usd": 32,  # tee invariant — shelf-enforced in production
    }


def coverage_of(case: dict[str, Any], echoed: dict[str, Any]) -> dict[str, Any]:
    """Which placement fields survived the round trip (pure; unit-tested)."""
    placement = echoed.get("placement", echoed) if isinstance(echoed, dict) else {}
    fields = ("design_type", "front", "back", "sleeve")
    kept = {f: placement.get(f) == case[f] for f in fields}
    colors = echoed.get("colorways") if isinstance(echoed, dict) else None
    return {
        "case": case,
        "kept": kept,
        "colorways_kept": list(colors or []) == list(case["colorways"]),
        "full_coverage": all(kept.values()) and list(colors or []) == list(case["colorways"]),
        "raw_response": echoed,
    }


async def _dry_run() -> dict[str, Any]:
    """Offline shape test: mocked echo tool — validates harness logic only."""
    rows = []
    for case in MATRIX:
        payload = build_draft_payload(case)
        assert payload["state"] == "DRAFT"  # never anything else in the spike
        rows.append(coverage_of(case, {"placement": dict(payload["placement"]),
                                       "colorways": list(payload["colorways"])}))
    return {"mode": "dry-run", "coverage": rows,
            "full_matrix_covered": all(r["full_coverage"] for r in rows)}


async def _live(url: str, token: str) -> dict[str, Any]:
    """Real MCP session: list tools, create one DRAFT per matrix case."""
    import httpx

    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    client = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=60.0)
    rows: list[dict[str, Any]] = []
    tools_seen: list[str] = []
    async with client:
        async with streamable_http_client(url) as transport:
            read, write, *_ = transport
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                tools_seen = [t.name for t in tools.tools]
                create_tool = next((t for t in tools_seen if t in CREATE_TOOL_CANDIDATES), None)
                if create_tool is None:
                    return {"mode": "live", "tools_seen": tools_seen,
                            "error": "no product-create tool on the MCP server — hand-rolled Open API is the v1 path",
                            "coverage": []}
                for case in MATRIX:
                    payload = build_draft_payload(case)
                    result = await session.call_tool(create_tool, payload)
                    texts = [b.text for b in (result.content or []) if hasattr(b, "text")]
                    try:
                        echoed = json.loads("".join(texts)) if texts else {}
                    except json.JSONDecodeError:
                        echoed = {"text": "".join(texts)}
                    rows.append(coverage_of(case, echoed))
    return {"mode": "live", "tools_seen": tools_seen, "coverage": rows,
            "full_matrix_covered": all(r["full_coverage"] for r in rows) if rows else False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fourthwall product-create spike (A13)")
    parser.add_argument("--dry-run", action="store_true", help="offline shape test (mocked)")
    parser.add_argument("--live", action="store_true", help="real MCP session, DRAFT only")
    args = parser.parse_args(argv)

    if args.live:
        url, token = os.environ.get("FOURTHWALL_MCP_URL", ""), os.environ.get("FOURTHWALL_MCP_TOKEN", "")
        if not url or not token:
            print("FOURTHWALL_MCP_URL/FOURTHWALL_MCP_TOKEN are required for --live", file=sys.stderr)
            return 2
        evidence = asyncio.run(_live(url, token))
    else:
        evidence = asyncio.run(_dry_run())
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
