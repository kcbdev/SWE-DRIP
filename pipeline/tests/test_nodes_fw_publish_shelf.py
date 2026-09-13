"""Nodes 9–11 contracts (spec C10, C2 nodes 9–11, phase lock C7).

Price-invariant matrix, retired/missing-contract rejection, publish-gate
interrupt with DRAFT phase lock, FW draft payload capture with the no-PUBLIC
guard — all offline with a mock client.
"""

from __future__ import annotations

from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from pipeline.graph import build_graph
from pipeline.nodes.fw_create import fw_create
from pipeline.nodes.publish_gate import publish_gate
from pipeline.nodes.shelf import PRICE_INVARIANTS, check_contract, check_price, shelf
from pipeline.routing import NODE_ORDER

COPY = {"slogan": "Ship It Live", "title": "Vibe Coding Tee",
        "description": "A dry joke.", "tags": ["vibe-coding"]}
SPEC = {"render_prompt": "a monochrome terminal", "style": "mono-log"}
RENDER = {"file_url": "runs/d-9/render.png", "model_used": "riverflow-v2-pro",
          "colorways_valid": []}

ACTIVE_CONTRACT = {"collection_id": "vibe-coding", "status": "active"}


class _MockFW:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.payloads: list[dict] = []
        self.response = {"id": "fw-1", "state": "DRAFT", **(response or {})}

    def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(payload)
        return dict(self.response)


def _cfg(**extra):
    return {"configurable": extra}


# ------------------------------------------------------------------ shelf


def test_price_invariants_are_founder_locked() -> None:
    assert PRICE_INVARIANTS == {"tee": 32.0, "hoodie": 62.0, "mug": 20.0}


@pytest.mark.parametrize(
    ("product_type", "price", "valid"),
    [
        ("tee", 32.0, True),
        ("tee", 32, True),
        ("tee", 31.99, False),
        ("tee", 33.0, False),
        ("hoodie", 62.0, True),
        ("hoodie", 60.0, False),
        ("mug", 20.0, True),
        ("mug", 0, False),
        ("poster", 32.0, False),
        ("tee", "32", False),
        ("tee", None, False),
    ],
)
def test_price_matrix(product_type, price, valid: bool) -> None:
    assert (check_price(product_type, price) == []) is valid


@pytest.mark.parametrize(
    ("contract", "fragment"),
    [
        ({"collection_id": "c", "status": "retired"}, "retired"),
        ({"collection_id": "c", "status": "draft"}, "not active"),
        ({"collection_id": "c", "status": "weird"}, "not active"),
        ({}, "no collection contract"),
    ],
)
def test_contract_rejections(contract: dict, fragment: str) -> None:
    assert any(fragment in e for e in check_contract(contract))


def test_shelf_accepts_valid_run() -> None:
    out = shelf(
        {"fw_product": {"product_type": "tee", "price": 32.0},
         "collection_contract": ACTIVE_CONTRACT},
        None,
    )
    assert out["shelf_result"]["accepted"] is True
    assert out["shelf_result"]["collection_id"] == "vibe-coding"
    assert "errors" not in out


def test_shelf_rejects_mismatch_without_crashing() -> None:
    out = shelf(
        {"fw_product": {"product_type": "tee", "price": 10.0},
         "collection_contract": {"collection_id": "c", "status": "retired"}},
        None,
    )
    assert out["shelf_result"]["accepted"] is False
    assert any("violates invariant" in e for e in out["errors"])
    assert any("retired" in e for e in out["errors"])
    assert out["visited"] == ["shelf"]


def test_shelf_missing_product_records_error() -> None:
    out = shelf({"collection_contract": ACTIVE_CONTRACT}, None)
    assert out["shelf_result"]["accepted"] is False


# ------------------------------------------------------------ publish gate


def test_publish_gate_interrupts() -> None:
    graph = build_graph(checkpointer=MemorySaver())
    off = {n: False for n in NODE_ORDER}
    paused = graph.invoke(
        {"design_id": "d-g"},
        {"configurable": {"thread_id": "gate", "hitl": {**off, "publish_gate": True}}},
    )
    assert "__interrupt__" in paused
    # The interrupting node's own update is discarded: visited stops at node 9.
    assert paused["visited"] == NODE_ORDER[:9]
    assert paused["__interrupt__"][0].value["node"] == "publish_gate"
    assert "PUBLIC" not in str(paused["__interrupt__"])


def test_publish_gate_resume_stays_draft() -> None:
    graph = build_graph(checkpointer=MemorySaver())
    off = {n: False for n in NODE_ORDER}
    base = {"thread_id": "gate-resume", "hitl": {**off, "publish_gate": True}}
    graph.invoke({"design_id": "d-g"}, {"configurable": base})
    # Resume keeps the gate flag on so the node re-reaches interrupt(), which
    # then returns the resume value instead of pausing (LangGraph semantics).
    resumed = graph.invoke(
        Command(resume={"approved": True, "note": "looks good"}),
        {"configurable": base},
    )
    decision = resumed["publish_decision"]
    assert decision["approved"] is True
    assert decision["state"] == "DRAFT"  # phase lock: approval never publishes
    assert decision["note"] == "looks good"


def test_publish_gate_flag_off_defaults_to_unapproved() -> None:
    # Explicit flags-off: bare None would apply the default-ON gate and pause.
    out = publish_gate(
        {"fw_product": {"id": "fw-1"}},
        {"configurable": {"hitl": {"publish_gate": False}}},  # type: ignore[typeddict-item]
    )
    assert out["publish_decision"] == {"approved": False, "state": "DRAFT", "product_id": "fw-1"}


# --------------------------------------------------------------- fw create


def _fw_state(**overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "design_id": "d-9",
        "collection_id": "vibe-coding",
        "listing_copy": COPY,
        "design_spec": SPEC,
        "render_result": RENDER,
    }
    state.update(overrides)
    return state


def test_fw_create_sends_exact_draft_payload() -> None:
    mock = _MockFW()
    out = fw_create(_fw_state(), _cfg(fw_client=mock, fw_live=True))
    assert len(mock.payloads) == 1
    payload = mock.payloads[0]
    assert payload == {
        "title": "Vibe Coding Tee",
        "description": "A dry joke.",
        "tags": ["vibe-coding"],
        "product_type": "tee",
        "price": 32.0,  # from PRICE_INVARIANTS, not a literal
        "state": "DRAFT",
        "render_file": "runs/d-9/render.png",
        "collection_id": "vibe-coding",
    }
    assert "PUBLIC" not in str(payload)
    product = out["fw_product"]
    assert product["sent"] is True and product["id"] == "fw-1" and product["state"] == "DRAFT"


def test_fw_create_flag_off_never_calls_client() -> None:
    mock = _MockFW()
    out = fw_create(_fw_state(), _cfg(fw_client=mock))
    assert mock.payloads == []
    assert out["fw_product"]["sent"] is False
    assert any("not sent" in e for e in out["errors"])


def test_fw_create_rejects_public_response_loudly() -> None:
    mock = _MockFW(response={"state": "PUBLIC"})
    with pytest.raises(ValueError, match="non-DRAFT"):
        fw_create(_fw_state(), _cfg(fw_client=mock, fw_live=True))


def test_fw_create_missing_inputs_record_errors() -> None:
    assert any("missing copy/spec/render" in e for e in fw_create({}, None)["errors"])
    assert any("no fw_client" in e for e in fw_create(_fw_state(), None)["errors"])
    out = fw_create(_fw_state(), _cfg(fw_client=_MockFW(), fw_live=True, product_type="poster"))
    assert any("unknown product_type" in e for e in out["errors"])


# ------------------------------------------------------- full-graph shape


def test_full_graph_ends_at_unpublished_draft() -> None:
    """PBI-014 manual-shape test, offline: mocked FW, DRAFT + price + rejection.

    The drafted contract is status draft (activation is PBI-020), so shelf
    honestly rejects while the FW draft itself is validly priced — exactly the
    phase-correct end state.
    """
    from pipeline.llm import OpenRouterClient
    import base64
    import httpx
    import json as jsonlib
    import struct

    ihdr = struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0)
    png = base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4
        + b"\x00\x00\x00\x00IEND"
    ).decode()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/generations"):
            return httpx.Response(200, json={"data": [{"b64_json": png}], "usage": {}})
        content = jsonlib.loads(request.content)["messages"][0]["content"]
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
            reply = {"style_cohesion": 80, "focal_point": 80, "placement_fit": 80, "contrast": 80}
        else:
            reply = {"rcao": "r", "render_prompt": "a monochrome terminal"}
        return httpx.Response(
            200, json={"choices": [{"message": {"content": jsonlib.dumps(reply)}}], "usage": {}}
        )

    class _Engine:
        def __init__(self) -> None:
            self.rows: list[dict] = []

        def begin(self):
            from contextlib import contextmanager
            engine = self

            @contextmanager
            def _cm():
                class _Conn:
                    def execute(self, stmt):
                        engine.rows.append(dict(stmt.compile().params))

                yield _Conn()

            return _cm()

    mock_fw = _MockFW()
    client = OpenRouterClient(api_key="test-key", transport=httpx.MockTransport(handler))
    import tempfile

    tmp = tempfile.mkdtemp()
    graph = build_graph(checkpointer=MemorySaver())
    result = graph.invoke(
        {"design_id": "d-full", "collection_id": "vibe-coding",
         "brief": {"subject": "Vibe Coding", "text": "x", "style": "mono-log"},
         "briefs": [
             {"id": "b1", "subject": "Vibe Coding", "text": "tee", "style": "mono-log",
              "engagement": 35, "novelty": 20, "specificity": 15},
             {"id": "b2", "subject": "Vibe Coding", "text": "hoodie", "style": "mono-log",
              "engagement": 30, "novelty": 20, "specificity": 12},
         ]},
        {"configurable": {"thread_id": "full-914", "hitl": {n: False for n in NODE_ORDER},
                           "llm_client": client, "cost_engine": _Engine(),
                           "run_dir": tmp, "design_type": "hero-icon",
                           "fw_client": mock_fw, "fw_live": True}},
    )
    assert result["visited"] == NODE_ORDER  # all 11 execute in the locked order
    product = result["fw_product"]
    assert product["sent"] is True and product["state"] == "DRAFT"
    assert product["price"] == 32.0
    assert result["publish_decision"] == {"approved": False, "state": "DRAFT", "product_id": "fw-1"}
    assert result["shelf_result"]["accepted"] is False  # draft contract, not active
    assert "PUBLIC" not in str(result)
