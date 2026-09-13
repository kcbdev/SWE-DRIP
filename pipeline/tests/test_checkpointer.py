"""A5 checkpointer evidence (spec C5): persisted run state matches §1.3.

Integration: requires DATABASE_URL (skipped offline). Uses mocked model/FW
layers — only Postgres is real.
"""

from __future__ import annotations

import base64
import json
import os
import struct
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requires DATABASE_URL (A5 integration)")

from pipeline.graph import build_graph
from pipeline.llm import OpenRouterClient
from pipeline.nodes.contract import validate_contract
from pipeline.nodes.shelf import PRICE_INVARIANTS
from pipeline.routing import NODE_ORDER
from pipeline.rubric import CRITERIA


def _png() -> str:
    ihdr = struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0)
    return base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4
        + b"\x00\x00\x00\x00IEND"
    ).decode()


def _mock_client() -> OpenRouterClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/generations"):
            return httpx.Response(200, json={"data": [{"b64_json": _png()}], "usage": {}})
        content = json.loads(request.content)["messages"][0]["content"]
        text = (
            " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            if isinstance(content, list)
            else content
        )
        if "thematic clusters" in text:
            reply: Any = {"clusters": [{"theme": "Vibe Coding", "brief_ids": ["b1", "b2"]}]  }
        elif "listing copy" in text:
            reply = {"slogan": "Ship It Live", "title": "Vibe Coding Tee",
                     "description": "A dry joke.", "tags": ["vibe-coding"]}
        elif "rubric" in text:
            reply = {c: 80 for c in CRITERIA}
        else:
            reply = {"rcao": "r", "render_prompt": "a monochrome terminal"}
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(reply)}}], "usage": {}}
        )

    return OpenRouterClient(api_key="a5-test", transport=httpx.MockTransport(handler))


class _MockFW:
    def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"id": "fw-a5", "state": "DRAFT"}


class _NullEngine:
    from contextlib import contextmanager

    @contextmanager
    def begin(self):
        class _Conn:
            def execute(self, stmt):
                return None

        yield _Conn()


async def test_full_run_state_matches_design_record(tmp_path) -> None:
    """A5: persisted checkpointer state carries the §1.3 design record."""
    from pipeline.checkpoint import get_checkpointer

    async with get_checkpointer() as saver:
        await saver.setup()
        graph = build_graph(checkpointer=saver)
        await graph.ainvoke(
            {
                "design_id": "a5-run",
                "collection_id": "vibe-coding",
                "brief": {"subject": "Vibe Coding", "text": "x", "style": "mono-log"},
                "briefs": [
                    {"id": "b1", "subject": "Vibe Coding", "text": "tee", "style": "mono-log",
                     "engagement": 35, "novelty": 20, "specificity": 15},
                    {"id": "b2", "subject": "Vibe Coding", "text": "hoodie", "style": "mono-log",
                     "engagement": 30, "novelty": 20, "specificity": 12},
                ],
            },
            {"configurable": {"thread_id": "a5-thread", "hitl": {n: False for n in NODE_ORDER},
                               "llm_client": _mock_client(), "cost_engine": _NullEngine(),
                               "run_dir": str(tmp_path), "design_type": "hero-icon",
                               "fw_client": _MockFW(), "fw_live": True}},
        )
        snapshot = await graph.aget_state({"configurable": {"thread_id": "a5-thread"}})
    values = snapshot.values
    # §1.3 design record present with the right shapes:
    assert values["design_id"] == "a5-run"
    assert set(values["brief"]) >= {"subject", "text", "style"}
    assert set(values["render"]) >= {"file_url", "model_used", "colorways_valid"}
    assert set(values["aesthetic_qc"]["scores"]) == set(CRITERIA)
    assert set(values["placement"]) == {"front", "back", "sleeve"} or values["placement"] == {}
    assert validate_contract(values["collection_contract"]) == []
    assert values["fw_product"]["price"] == PRICE_INVARIANTS["tee"]
    assert "PUBLIC" not in json.dumps(values, default=str)
