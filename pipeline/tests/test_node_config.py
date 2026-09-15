"""Per-node runtime config contracts (spec C1/C2).

The empty store MUST behave exactly like the pre-config code, or this whole
control plane silently changes pipeline behaviour on upgrade.
"""

from __future__ import annotations

from typing import Any

import pytest

from pipeline.node_config import (
    NodeConfig,
    NodeConfigError,
    default_node_config,
    effective_for_config,
    resolve_all_node_configs,
    resolve_node_config,
)
from pipeline.routing import MODEL_FOR_NODE, NODE_ORDER


# --------------------------------------------------------------- defaults


def test_empty_store_is_byte_identical_to_code_defaults() -> None:
    for node in NODE_ORDER:
        resolved = resolve_node_config(node, {})
        assert resolved == default_node_config(node)
        # Nothing marked as overridden, so the UI can say "default" honestly.
        assert resolved.overridden == frozenset()
        assert resolved.model_source == "default"
        assert resolved.params == {}
        assert resolved.prompt_override is None
        assert resolved.enabled is True


def test_all_node_configs_cover_the_locked_order() -> None:
    configs = resolve_all_node_configs({})
    assert list(configs) == NODE_ORDER
    assert configs["trend_research"].model == MODEL_FOR_NODE["trend_research"]
    # Deterministic/external nodes legitimately have no model.
    assert configs["placement"].model is None


def test_unknown_node_is_loud() -> None:
    with pytest.raises(NodeConfigError):
        default_node_config("not-a-node")


# --------------------------------------------------------------- overrides


def test_model_override_wins_and_is_marked() -> None:
    conf = resolve_node_config("trend_research", {"trend_research": {"model": "x/y"}})
    assert conf.model == "x/y"
    assert conf.model_source == "store"
    assert conf.overridden == frozenset({"model"})
    # Untouched fields keep their defaults.
    assert conf.params == {} and conf.enabled is True


def test_partial_override_keeps_other_defaults() -> None:
    conf = resolve_node_config(
        "listing_copy", {"listing_copy": {"params": {"temperature": 0.2}}}
    )
    assert conf.params == {"temperature": 0.2}
    assert conf.model == MODEL_FOR_NODE["listing_copy"]  # still the default
    assert conf.overridden == frozenset({"params"})


def test_prompt_override_and_enabled_flag() -> None:
    conf = resolve_node_config(
        "aesthetic_qc",
        {"aesthetic_qc": {"prompt_override": "Score it harshly.", "enabled": False}},
    )
    assert conf.prompt_override == "Score it harshly."
    assert conf.enabled is False
    assert conf.overridden == frozenset({"prompt_override", "enabled"})


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("model", 42),
        ("model", "   "),
        ("params", ["not", "a", "dict"]),
        ("params", {1: "non-string key"}),
        ("prompt_override", 5),
        ("prompt_override", "  "),
        ("enabled", "yes"),
    ],
)
def test_malformed_override_is_ignored_and_named(field: str, bad_value: Any) -> None:
    """A bad store value must never take a run down — it falls back and is named."""
    conf = resolve_node_config("trend_research", {"trend_research": {field: bad_value}})
    fresh = default_node_config("trend_research")
    assert field in conf.ignored_invalid
    assert field not in conf.overridden
    # Every effective value is the default; only the "ignored" note differs.
    assert conf.model == fresh.model
    assert conf.params == fresh.params
    assert conf.prompt_override == fresh.prompt_override
    assert conf.enabled == fresh.enabled


def test_enabled_false_is_valid_not_malformed() -> None:
    conf = resolve_node_config("shelf", {"shelf": {"enabled": False}})
    assert conf.enabled is False
    assert conf.ignored_invalid == ()


# --------------------------------------------------- effective_for_config


def test_node_reads_frozen_snapshot_from_config() -> None:
    snapshot = {"trend_research": {"model": "frozen/model", "params": {"temperature": 1.0}}}
    conf = effective_for_config({"node_config": snapshot}, "trend_research")
    assert conf.model == "frozen/model"
    assert conf.params == {"temperature": 1.0}


def test_bare_config_falls_back_to_defaults() -> None:
    """A run that predates the snapshot (or a test with a bare config) still works."""
    assert effective_for_config({}, "trend_research") == default_node_config("trend_research")
    assert effective_for_config(None, "listing_copy") == default_node_config("listing_copy")


def test_snapshot_dict_does_not_leak_a_stale_node_config_type() -> None:
    """The snapshot may arrive as plain dicts (checkpointer round-trip)."""
    conf = effective_for_config(
        {"node_config": {"art_render": {"model": "img/model", "enabled": False}}},
        "art_render",
    )
    assert isinstance(conf, NodeConfig)
    assert conf.model == "img/model"
    assert conf.enabled is False


def test_resolution_is_frozen_at_start_not_read_live() -> None:
    """A later store edit must not change an in-flight run's config (C2)."""
    frozen = resolve_all_node_configs({"trend_research": {"model": "first/model"}})
    snapshot = {node: conf.as_dict() for node, conf in frozen.items()}
    # Store changes AFTER the snapshot was taken.
    later = {"trend_research": {"model": "second/model"}}
    assert resolve_node_config("trend_research", later).model == "second/model"
    # The frozen snapshot is unaffected.
    assert effective_for_config({"node_config": snapshot}, "trend_research").model == "first/model"
