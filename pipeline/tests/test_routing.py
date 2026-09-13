"""Routing-table contracts (spec C3, acceptance A6 unit layer).

`routing.py` is the single source of model IDs. These tests prove every node
is covered, the IDs are exactly the data-spec §3 values, deterministic nodes
make no model call (None), and the client sends precisely the routed model —
the deterministic guard against the POC's single-model-override bug. (The
full per-node A6 harness with real node functions lands in PBI-015.)
"""

from __future__ import annotations

import json

import httpx
import pytest

from pipeline.llm import OpenRouterClient
from pipeline.routing import (
    CLAUDE_SONNET,
    GEMINI_FLASH,
    IMAGE_FALLBACKS,
    MODEL_FOR_NODE,
    NODE_ORDER,
    RIVERFLOW_PRO,
    model_for,
)

# Exact data-spec §3 IDs per model-backed node.
EXPECTED_MODELS: dict[str, str] = {
    "trend_research": GEMINI_FLASH,
    "contract_approval": CLAUDE_SONNET,
    "listing_copy": CLAUDE_SONNET,
    "design_spec": CLAUDE_SONNET,
    "art_render": RIVERFLOW_PRO,
    "aesthetic_qc": GEMINI_FLASH,
}

# Nodes that must never make a model call (C8 + external/HITL nodes).
MODEL_FREE_NODES = ["placement", "technical_qc", "fw_create", "publish_gate", "shelf"]


def test_routing_covers_all_eleven_nodes() -> None:
    assert set(MODEL_FOR_NODE) == set(NODE_ORDER)
    assert len(NODE_ORDER) == 11


@pytest.mark.parametrize(("node", "model"), sorted(EXPECTED_MODELS.items()))
def test_routed_model_ids_are_exact(node: str, model: str) -> None:
    assert model_for(node) == model


@pytest.mark.parametrize("node", MODEL_FREE_NODES)
def test_deterministic_and_external_nodes_make_no_model_call(node: str) -> None:
    assert model_for(node) is None


def test_art_render_fallbacks_from_spec() -> None:
    assert IMAGE_FALLBACKS == ("gpt-5-image-mini", "seedream")


def test_unknown_node_is_loud() -> None:
    with pytest.raises(KeyError):
        model_for("nope_not_a_node")


def _transport(captured: list[dict], response: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=response)

    return httpx.MockTransport(handler)


CHAT_RESPONSE = {
    "choices": [{"message": {"content": "ok"}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}


@pytest.mark.parametrize("node", sorted(EXPECTED_MODELS))
def test_client_sends_exactly_the_routed_model(node: str) -> None:
    """A6 unit layer: captured per-call model == routing-table entry."""
    captured: list[dict] = []
    client = OpenRouterClient(api_key="test-key", transport=_transport(captured, CHAT_RESPONSE))
    result = client.chat(model=model_for(node), messages=[{"role": "user", "content": "hi"}])  # type: ignore[arg-type]
    assert captured[0]["model"] == EXPECTED_MODELS[node]
    assert result.model == EXPECTED_MODELS[node]
    assert (result.tokens_in, result.tokens_out) == (10, 5)


def test_vision_call_shape() -> None:
    captured: list[dict] = []
    client = OpenRouterClient(api_key="test-key", transport=_transport(captured, CHAT_RESPONSE))
    client.vision(model=model_for("aesthetic_qc"), prompt="score it", image_url="http://x/y.png")  # type: ignore[arg-type]
    content = captured[0]["messages"][0]["content"]
    assert captured[0]["model"] == GEMINI_FLASH
    assert {"type": "image_url", "image_url": {"url": "http://x/y.png"}} in content


def test_image_call_shape() -> None:
    captured: list[dict] = []
    response = {"data": [{"url": "http://x/y.png"}], "usage": {}}
    client = OpenRouterClient(api_key="test-key", transport=_transport(captured, response))
    result = client.image(model=model_for("art_render"), prompt="a tee")  # type: ignore[arg-type]
    assert captured[0] == {"model": RIVERFLOW_PRO, "prompt": "a tee"}
    assert result.content == "http://x/y.png"


def test_missing_api_key_is_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        OpenRouterClient()
