"""A6 routing audit (spec C6): every model call in a full run uses its node's
routed model — the deterministic firewall against the POC's single-model-
override bug. Offline with a capturing transport; FW stays mocked (it makes
no model calls by construction).
"""

from __future__ import annotations

import base64
import json
import struct
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
from langgraph.checkpoint.memory import MemorySaver

from pipeline.graph import build_graph
from pipeline.llm import OpenRouterClient
from pipeline.routing import (
    CLAUDE_SONNET,
    GEMINI_FLASH_IMAGE,
    GEMINI_FLASH_LITE,
    MODEL_FOR_NODE,
    NODE_ORDER,
)
from pipeline.rubric import CRITERIA

# (node, model): exact expected call counts for a clean single-pass run.
EXPECTED_CALLS: dict[tuple[str, str], int] = {
    ("trend_research", GEMINI_FLASH_LITE): 1,
    ("listing_copy", CLAUDE_SONNET): 1,
    ("design_spec", CLAUDE_SONNET): 1,
    ("art_render", GEMINI_FLASH_IMAGE): 1,
    ("aesthetic_qc", GEMINI_FLASH_LITE): 1,
}

MODEL_BACKED_NODES = {node for node, model in MODEL_FOR_NODE.items() if model is not None}


def _png() -> str:
    ihdr = struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0)
    return base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4
        + b"\x00\x00\x00\x00IEND"
    ).decode()


def _auditing_transport(captured: list[tuple[str, str]]) -> httpx.MockTransport:
    def attribute(body: dict[str, Any]) -> str:
        content = body["messages"][0]["content"]
        text = (
            " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            if isinstance(content, list)
            else content
        )
        if "thematic clusters" in text:
            return "trend_research"
        if "listing copy" in text:
            return "listing_copy"
        if "RCAO" in text:
            return "design_spec"
        return "aesthetic_qc"  # rubric prompt

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path.endswith("/images/generations"):
            captured.append(("art_render", body.get("model", "")))
            return httpx.Response(200, json={"data": [{"b64_json": _png()}], "usage": {}})
        node = attribute(body)
        captured.append((node, body.get("model", "")))
        if node == "trend_research":
            reply: Any = {"clusters": [{"theme": "Vibe Coding", "brief_ids": ["b1", "b2"]}]  }
        elif node == "listing_copy":
            reply = {"slogan": "Ship It Live", "title": "Vibe Coding Tee",
                     "description": "A dry joke.", "tags": ["vibe-coding"]}
        elif node == "design_spec":
            reply = {"rcao": "r", "render_prompt": "a monochrome terminal"}
        else:
            reply = {c: 80 for c in CRITERIA}
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(reply)}}], "usage": {}}
        )

    return httpx.MockTransport(handler)


class _NullEngine:
    @contextmanager
    def begin(self):
        class _Conn:
            def execute(self, stmt):
                return None

        yield _Conn()


class _MockFW:
    def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"id": "fw-a6", "state": "DRAFT"}


def test_full_run_models_match_routing_table(tmp_path: Path) -> None:
    captured: list[tuple[str, str]] = []
    client = OpenRouterClient(api_key="a6-test", transport=_auditing_transport(captured))
    graph = build_graph(checkpointer=MemorySaver())
    graph.invoke(
        {
            "design_id": "a6-run",
            "brief": {"subject": "Vibe Coding", "text": "x", "style": "mono-log"},
            "briefs": [
                {"id": "b1", "subject": "Vibe Coding", "text": "tee", "style": "mono-log",
                 "engagement": 35, "novelty": 20, "specificity": 15},
                {"id": "b2", "subject": "Vibe Coding", "text": "hoodie", "style": "mono-log",
                 "engagement": 30, "novelty": 20, "specificity": 12},
            ],
        },
        {"configurable": {"thread_id": "a6-thread", "hitl": {n: False for n in NODE_ORDER},
                           "llm_client": client, "cost_engine": _NullEngine(),
                           "run_dir": str(tmp_path), "design_type": "hero-icon",
                           "fw_client": _MockFW(), "fw_live": True}},
    )
    # Every captured call used exactly its node's routed model:
    for node, model in captured:
        assert model == MODEL_FOR_NODE[node], f"{node} used {model!r}"
    # Exact call multiset: no missing, no extra, no silent override:
    tallied: dict[tuple[str, str], int] = {}
    for key in captured:
        tallied[key] = tallied.get(key, 0) + 1
    assert tallied == EXPECTED_CALLS
    # The POC bug (one model for everything) is structurally impossible here:
    assert len({model for _, model in captured}) > 1
    # Model-free nodes made no model calls:
    assert {node for node, _ in captured} <= MODEL_BACKED_NODES
