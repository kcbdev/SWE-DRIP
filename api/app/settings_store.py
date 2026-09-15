"""Runtime settings store — key/value JSON backed by Postgres (spec C5).

Provides typed accessors for HITL flags, brand-lock constants, and
integrations credentials/status. The pipeline reads HITL flags and the
OpenRouter key via this module at run start (pipeline/settings.py). All
accessors are pure except the DB-touching get/set helpers. Tests mock or
bypass the DB layer.

Integration credentials are stored as one JSON row in ``settings`` so an admin
can configure Fourthwall/OpenRouter from the Control Panel; a stored value
takes precedence over the matching environment variable. Secret fields are
never returned by the API (presence only).

The store is DB-optional: when DATABASE_URL is not configured, accessors
return in-memory defaults. This keeps unit tests fully offline.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Defaults (mirrors migration 0004 seeds)
# ---------------------------------------------------------------------------

_DEFAULT_HITL: dict[str, bool] = {
    "trend_research": False,
    "contract_approval": True,
    "listing_copy": False,
    "design_spec": False,
    "art_render": False,
    "placement": False,
    "aesthetic_qc": True,
    "technical_qc": False,
    "fw_create": False,
    "publish_gate": True,
    "shelf": False,
}

_DEFAULT_BRAND: dict[str, Any] = {
    "palette": {"void_black": "#0D0D0D", "terminal_green": "#00FF41"},
    "typeface": "JetBrains Mono",
    "forbidden": ["gradients", "shadows", "rounded_pills", "pastels"],
}

# In-memory cache (DB-backed when available, pure fallback otherwise).
_cache: dict[str, Any] = {}
_cache_loaded = False


def _db_available() -> bool:
    """Check if DATABASE_URL is configured without importing at module level."""
    try:
        from .config import settings as cfg
        return bool(cfg.database_url)
    except Exception:
        return False


def _load_from_db() -> None:
    """Load all settings from the DB into the in-memory cache."""
    global _cache_loaded
    if _cache_loaded or not _db_available():
        return
    try:
        from .db import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT key, value_json FROM settings")).mappings().all()
        for row in rows:
            _cache[row["key"]] = row["value_json"]
        _cache_loaded = True
    except Exception:
        _cache_loaded = True  # Don't retry on every call


def _write_to_db(key: str, value: Any) -> None:
    """Upsert a setting to the DB."""
    if not _db_available():
        return
    from .db import get_engine
    import json

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(_upsert_statement(), {"key": key, "val": json.dumps(value)})


def _upsert_statement() -> Any:
    """Return the settings upsert statement.

    Uses ``CAST(:val AS jsonb)`` rather than the Postgres ``::`` shorthand:
    SQLAlchemy's ``text()`` bind-parameter parser does not recognise ``:val``
    when it is immediately followed by ``:``, so ``:val::jsonb`` is emitted
    verbatim and Postgres rejects the statement ("syntax error at or near :").
    """
    from sqlalchemy import text

    return text(
        "INSERT INTO settings (key, value_json, updated_at) "
        "VALUES (:key, CAST(:val AS jsonb), now()) "
        "ON CONFLICT (key) DO UPDATE SET "
        "value_json = CAST(:val AS jsonb), updated_at = now()"
    )


# ---------------------------------------------------------------------------
# HITL flags
# ---------------------------------------------------------------------------

def get_hitl_flags() -> dict[str, bool]:
    """Return the current HITL flag state for all nodes."""
    _load_from_db()
    raw = _cache.get("hitl", _DEFAULT_HITL)
    # Merge with defaults so new nodes are always present.
    merged = {**_DEFAULT_HITL, **raw}
    return {k: bool(v) for k, v in merged.items()}


def set_hitl_flags(flags: dict[str, bool]) -> None:
    """Write HITL flags to the cache and DB."""
    current = get_hitl_flags()
    current.update(flags)
    _cache["hitl"] = current
    _write_to_db("hitl", current)


def get_hitl_flag(node: str) -> bool:
    """Return the HITL flag for a single node."""
    return get_hitl_flags().get(node, _DEFAULT_HITL.get(node, False))


# ---------------------------------------------------------------------------
# Brand-lock constants
# ---------------------------------------------------------------------------

def get_brand() -> dict[str, Any]:
    """Return the brand-lock constants."""
    _load_from_db()
    raw = _cache.get("brand", _DEFAULT_BRAND)
    merged = {**_DEFAULT_BRAND, **raw}
    if "palette" in raw and "palette" in _DEFAULT_BRAND:
        merged["palette"] = {**_DEFAULT_BRAND["palette"], **raw["palette"]}
    return merged


def set_brand(brand: dict[str, Any]) -> None:
    """Write brand-lock constants to the cache and DB."""
    current = get_brand()
    if "palette" in brand:
        current["palette"] = {**current.get("palette", {}), **brand["palette"]}
    for key in ("typeface", "forbidden"):
        if key in brand:
            current[key] = brand[key]
    _cache["brand"] = current
    _write_to_db("brand", current)


# ---------------------------------------------------------------------------
# Integration credentials (admin-configurable, DB over env)
# ---------------------------------------------------------------------------

_INTEGRATIONS_KEY = "integrations_credentials"

# Credential field -> Pydantic Settings attribute used as the env fallback.
_CREDENTIAL_ENV_FALLBACK: dict[str, str] = {
    "fourthwall_mcp_url": "fourthwall_mcp_url",
    "fourthwall_mcp_token": "fourthwall_mcp_token",
    "openrouter_api_key": "openrouter_api_key",
    "openrouter_base_url": "openrouter_base_url",
}

# Never echoed by the API — presence only.
SECRET_CREDENTIAL_FIELDS = ("fourthwall_mcp_token", "openrouter_api_key")

OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def get_integration_credentials() -> dict[str, str]:
    """Return stored (non-empty) credential overrides from the settings store."""
    _load_from_db()
    raw = _cache.get(_INTEGRATIONS_KEY) or {}
    if not isinstance(raw, dict):
        return {}
    return {
        name: value
        for name, value in raw.items()
        if isinstance(value, str) and value
    }


def set_integration_credentials(patch: dict[str, Any]) -> dict[str, str]:
    """Merge a credential patch into the store. An empty string clears a field.

    Only known credential fields are accepted; unknown keys are ignored so a
    typo cannot silently write junk into the config row. Secrets are never
    logged or returned by callers.
    """
    current = dict(get_integration_credentials())
    for name, value in patch.items():
        if name not in _CREDENTIAL_ENV_FALLBACK:
            continue
        if value is None:
            continue
        if value == "":
            current.pop(name, None)
        else:
            current[name] = str(value)
    _cache[_INTEGRATIONS_KEY] = current
    _write_to_db(_INTEGRATIONS_KEY, current)
    return current


def resolve_integration(name: str, default: str = "") -> str:
    """Resolve one credential: settings store first, environment second.

    The Control Panel settings UI is the runtime source of truth (spec C5), so
    a value saved there wins over the deployment env var; env remains the
    bootstrap/fallback path. Never raises — resolution failures degrade to the
    env value or *default*.
    """
    try:
        stored = get_integration_credentials().get(name)
    except Exception:
        stored = None
    if stored:
        return stored
    try:
        from .config import settings as cfg
    except Exception:
        return default
    attribute = _CREDENTIAL_ENV_FALLBACK.get(name)
    env_value = getattr(cfg, attribute, "") if attribute else ""
    return env_value or default


def get_integrations() -> dict[str, Any]:
    """Return integration presence plus non-secret endpoint hints.

    Contract: booleans for configured status, strings ONLY for non-secret
    endpoints. Tokens/keys are never included (asserted by tests).
    """
    fourthwall_url = resolve_integration("fourthwall_mcp_url")
    fourthwall_token = resolve_integration("fourthwall_mcp_token")
    openrouter_key = resolve_integration("openrouter_api_key")
    return {
        "fourthwall_mcp": bool(fourthwall_url and fourthwall_token),
        "openrouter": bool(openrouter_key),
        "fourthwall_mcp_url": fourthwall_url,
        "openrouter_base_url": resolve_integration(
            "openrouter_base_url", OPENROUTER_DEFAULT_BASE_URL
        ),
    }


# ---------------------------------------------------------------------------
# Generic setting accessors (used by agents module)
# ---------------------------------------------------------------------------

def get_setting(key: str, default: Any = None) -> Any:
    """Return any settings key, falling back to *default*."""
    _load_from_db()
    return _cache.get(key, default)


def set_setting(key: str, value: Any) -> None:
    """Write any settings key to the cache and DB."""
    _cache[key] = value
    _write_to_db(key, value)


# ---------------------------------------------------------------------------
# Reset (for tests)
# ---------------------------------------------------------------------------

def reset_cache() -> None:
    """Clear the in-memory cache (used by tests)."""
    global _cache, _cache_loaded
    _cache.clear()
    _cache_loaded = False
