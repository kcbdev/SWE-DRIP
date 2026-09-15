"""Per-node runtime configuration — the operator control plane (spec C1/C2).

`pipeline/routing.py` holds the **defaults** (the reviewed baseline and the
source of each node's model *class*). This module layers store overrides on top:

    code defaults  <  settings store (`node_config`)

Why this exists: routing IDs used to be hardcoded, and the first live run proved
every one of them was absent from OpenRouter's catalog (`google/gemini-2.0-flash-001`
→ 404). Model choice, generation params, prompt overrides and an enabled flag are
now operator-configurable, so a model change is a settings edit rather than a
deploy. `node_config` is resolved **once at run start** and frozen into the run —
editing config never changes a run in flight (same rule as HITL flags).

An empty store resolves to byte-identical defaults, so nothing here changes
behaviour until someone opts in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .routing import MODEL_FOR_NODE, NODE_ORDER

SETTINGS_KEY = "node_config"

CONFIG_FIELDS = ("model", "params", "prompt_override", "enabled")


class NodeConfigError(ValueError):
    """Unknown node — a programming error, never a user-input error."""


@dataclass(frozen=True)
class NodeConfig:
    """One node's effective runtime configuration."""

    node: str
    model: Optional[str]
    params: dict[str, Any]
    prompt_override: Optional[str]
    enabled: bool
    #: Which fields came from the store rather than the code defaults. Lets the
    #: UI say "overridden" honestly instead of guessing.
    overridden: frozenset[str] = frozenset()
    #: Overrides that were present but malformed; ignored at resolution time and
    #: surfaced so a bad store value is visible rather than silently swallowed.
    ignored_invalid: tuple[str, ...] = ()

    @property
    def model_source(self) -> str:
        return "store" if "model" in self.overridden else "default"

    def as_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "model": self.model,
            "params": dict(self.params),
            "prompt_override": self.prompt_override,
            "enabled": self.enabled,
            "overridden": sorted(self.overridden),
            "ignored_invalid": list(self.ignored_invalid),
        }


def default_node_config(node: str) -> NodeConfig:
    """The code-default configuration for ``node``."""
    if node not in MODEL_FOR_NODE:
        raise NodeConfigError(f"unknown pipeline node: {node!r}")
    return NodeConfig(
        node=node, model=MODEL_FOR_NODE[node], params={}, prompt_override=None, enabled=True
    )


def _valid_model(value: Any) -> bool:
    return value is None or (isinstance(value, str) and bool(value.strip()))


def _valid_params(value: Any) -> bool:
    return isinstance(value, dict) and all(isinstance(k, str) for k in value)


def _valid_prompt(value: Any) -> bool:
    return value is None or (isinstance(value, str) and bool(value.strip()))


def resolve_node_config(
    node: str, overrides: Optional[dict[str, Any]] = None
) -> NodeConfig:
    """Resolve ``node``'s config: code defaults overlaid with store values.

    A malformed field is ignored (the default wins) and named in
    ``ignored_invalid`` — resolution never raises on store content, so a bad
    settings row cannot take a run down. Write-time validation (PBI-040) is what
    stops bad values from being stored in the first place.
    """
    base = default_node_config(node)
    raw = (overrides or {}).get(node)
    if not isinstance(raw, dict):
        return base

    values: dict[str, Any] = {
        "model": base.model,
        "params": dict(base.params),
        "prompt_override": base.prompt_override,
        "enabled": base.enabled,
    }
    accepted: set[str] = set()
    ignored: list[str] = []

    if "model" in raw:
        if _valid_model(raw["model"]):
            values["model"] = raw["model"].strip() if isinstance(raw["model"], str) else None
            accepted.add("model")
        else:
            ignored.append("model")
    if "params" in raw:
        if _valid_params(raw["params"]):
            values["params"] = dict(raw["params"])
            accepted.add("params")
        else:
            ignored.append("params")
    if "prompt_override" in raw:
        if _valid_prompt(raw["prompt_override"]):
            values["prompt_override"] = raw["prompt_override"]
            accepted.add("prompt_override")
        else:
            ignored.append("prompt_override")
    if "enabled" in raw:
        if isinstance(raw["enabled"], bool):
            values["enabled"] = raw["enabled"]
            accepted.add("enabled")
        else:
            ignored.append("enabled")

    return NodeConfig(
        node=node,
        model=values["model"],
        params=values["params"],
        prompt_override=values["prompt_override"],
        enabled=values["enabled"],
        overridden=frozenset(accepted),
        ignored_invalid=tuple(ignored),
    )


def load_overrides() -> dict[str, Any]:
    """Store overrides, or ``{}`` when the store is unavailable.

    The store lives in the API package; importing it lazily keeps this module
    usable from the pipeline standalone (offline gates, parity harness).
    """
    try:
        from api.app.settings_store import get_setting

        raw = get_setting(SETTINGS_KEY, {})
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def resolve_all_node_configs(
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, NodeConfig]:
    """Resolve every node in locked order (the run-start snapshot)."""
    raw = load_overrides() if overrides is None else overrides
    return {node: resolve_node_config(node, raw) for node in NODE_ORDER}


def effective_for_config(configurable: Optional[dict[str, Any]], node: str) -> NodeConfig:
    """The config a node should honour, from ``config['configurable']['node_config']``.

    Falls back to code defaults when a run predates the config snapshot (or a
    test invokes a node with a bare config), so nodes never need a second
    lookup path.
    """
    snapshot = (configurable or {}).get("node_config") or {}
    entry = snapshot.get(node)
    if isinstance(entry, NodeConfig):
        return entry
    if isinstance(entry, dict):
        return NodeConfig(
            node=node,
            model=entry.get("model", MODEL_FOR_NODE.get(node)),
            params=dict(entry.get("params") or {}),
            prompt_override=entry.get("prompt_override"),
            enabled=bool(entry.get("enabled", True)),
            overridden=frozenset(entry.get("overridden") or ()),
        )
    return default_node_config(node)
