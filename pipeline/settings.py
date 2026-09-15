"""Pipeline settings resolution — reads from the Control Panel settings store.

The pipeline consumes HITL flags and the OpenRouter API key from the
``settings`` DB table via ``api.app.settings_store``. When the store is
unavailable (different process boundary, no DB), falls back to the hardcoded
DEFAULT_HITL in ``pipeline/graph.py`` and the environment.

This module is the single bridge between the pipeline runtime and the
settings store (spec C5, NFR-1). No shadow config files.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# Ensure the api package is importable when running from repo root.
_api_root = str(Path(__file__).resolve().parent.parent / "api")
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

from pipeline.graph import DEFAULT_HITL  # noqa: E402


def resolve_hitl_flags() -> dict[str, bool]:
    """Return the current HITL flags from the settings store, or defaults.

    This is called once at pipeline run start. The result is baked into
    the graph config and does not change mid-run.
    """
    try:
        from api.app.settings_store import get_hitl_flags
        return get_hitl_flags()
    except Exception:
        # Store unavailable — use hardcoded defaults.
        return dict(DEFAULT_HITL)


def is_hitl_enabled(node: str) -> bool:
    """Check if a specific node's HITL gate is enabled."""
    return resolve_hitl_flags().get(node, DEFAULT_HITL.get(node, False))


def resolve_openrouter_api_key() -> str:
    """Resolve the OpenRouter key: settings store (admin UI) first, env second.

    Returns "" when neither is configured — callers raise their own loud error
    rather than receiving a silent empty credential.
    """
    try:
        from api.app.settings_store import resolve_integration

        value = resolve_integration("openrouter_api_key")
        if value:
            return value
    except Exception:
        pass
    return os.environ.get("OPENROUTER_API_KEY", "")


def resolve_openrouter_base_url() -> str:
    """Resolve the OpenRouter base URL: settings store first, env second."""
    try:
        from api.app.settings_store import resolve_integration

        value = resolve_integration("openrouter_base_url")
        if value:
            return value
    except Exception:
        pass
    return os.environ.get("OPENROUTER_BASE_URL", "")
