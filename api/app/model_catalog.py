"""OpenRouter model catalog — live validation for the agent control plane (spec C3).

Why this exists: the first live run proved every hardcoded model ID was absent
from OpenRouter's catalog (``google/gemini-2.0-flash-001`` → 404). A model may
now only be saved when the ID is present in the live catalog; free-text IDs are
rejected with the closest matches. This module is the enforcement point's
source of truth.

Contract (PBI-040):

- ``list_models(query=None)`` — normalized rows
  (``id, name, context_length, prompt/completion price per M, input modalities``);
  never raises, never needs credentials (the models endpoint is public).
- ``model_exists(id)`` — exact ID match against the last verified data.
- ``closest(query, limit=3)`` — suggestions for rejection messages.
- A fetch failure degrades to the last good cache for *reads*; when there is no
  cache the catalog reports itself unavailable explicitly.
- Refinement rule: a stale cache may serve *reads* but must never authorise a
  *write*. ``verify_for_write()`` forces a refresh and raises
  ``CatalogUnavailable`` when the catalog cannot be verified — the write path
  refuses instead of accepting blindly.

Offline-safe: importing this module performs no network I/O; tests inject fake
payloads via ``_install_test_cache()`` or by monkeypatching ``_fetch_live``.
"""

from __future__ import annotations

import difflib
import time
from typing import Any, Optional

import httpx

MODELS_URL = "https://openrouter.ai/api/v1/models"

# Reads older than this are "stale": still served for GETs, never trusted for
# writes (the write path forces a refresh first).
TTL_SECONDS = 3600.0

_FETCH_TIMEOUT = 15.0


class CatalogUnavailable(RuntimeError):
    """The catalog cannot be verified right now (no cache + fetch failed, or a
    stale cache whose refresh failed at write time). Callers refuse the write
    and say so — they never accept blindly."""


# In-memory cache: the last good fetch. ``fetched_at`` is ``None`` until the
# first successful fetch; ``models`` are normalized rows (see ``_normalize``).
_cache: dict[str, Any] = {"fetched_at": None, "models": [], "by_id": {}}


def reset_cache() -> None:
    """Clear the in-memory cache (used by tests)."""
    _cache["fetched_at"] = None
    _cache["models"] = []
    _cache["by_id"] = {}


def _install_test_cache(rows: list[dict[str, Any]]) -> None:
    """Install normalized rows as a fresh cache (test helper, offline)."""
    normalized = [_normalize_row(r) for r in rows]
    # _normalize_row expects raw OpenRouter shapes; test rows may already be
    # normalized — accept both by passing through rows that already carry an id.
    normalized = [r for r in normalized if r.get("id")]
    _cache["models"] = normalized
    _cache["by_id"] = {r["id"]: r for r in normalized}
    _cache["fetched_at"] = time.time()


def _now() -> float:
    return time.time()


def _is_fresh() -> bool:
    fetched_at = _cache.get("fetched_at")
    if not fetched_at:
        return False
    try:
        return (_now() - float(fetched_at)) < TTL_SECONDS
    except (TypeError, ValueError):
        return False


def _has_cache() -> bool:
    return bool(_cache.get("models"))


def _price_per_m(raw: Any) -> Optional[float]:
    """OpenRouter prices are per-token strings; the picker shows per-million."""
    try:
        if raw is None:
            return None
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value * 1_000_000


def _normalize_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one raw OpenRouter model entry (or an already-normalized row).

    Tolerates missing keys — the catalog is third-party data and must never
    break a request. Already-normalized rows (with ``id`` and no ``pricing``
    dict) pass through with defaults filled.
    """
    if not isinstance(raw, dict):
        return {}
    model_id = raw.get("id")
    if not isinstance(model_id, str) or not model_id.strip():
        return {}
    pricing = raw.get("pricing") if isinstance(raw.get("pricing"), dict) else {}
    architecture = raw.get("architecture") if isinstance(raw.get("architecture"), dict) else {}
    input_modalities = architecture.get("input_modalities")
    if not isinstance(input_modalities, list):
        # Some entries use ``modality`` (e.g. "text+image->text"); keep the raw
        # hint when the structured list is absent.
        modality = architecture.get("modality")
        input_modalities = [modality] if isinstance(modality, str) and modality else []
    else:
        input_modalities = [m for m in input_modalities if isinstance(m, str)]
    context_length = raw.get("context_length")
    if isinstance(context_length, bool) or not isinstance(context_length, (int, float)):
        context_length = None
    elif isinstance(context_length, float):
        context_length = int(context_length)
    return {
        "id": model_id.strip(),
        "name": raw.get("name") if isinstance(raw.get("name"), str) else model_id.strip(),
        "context_length": context_length,
        "prompt_price_per_m": _price_per_m(pricing.get("prompt")),
        "completion_price_per_m": _price_per_m(pricing.get("completion")),
        "input_modalities": input_modalities,
    }


def _fetch_live() -> list[dict[str, Any]]:
    """Fetch the raw model list from OpenRouter (public endpoint, no key).

    Raises on any failure — callers translate that into stale-cache or
    unavailable outcomes so a request never 500s on catalog trouble.
    """
    # Do NOT send the OpenRouter key here: the models endpoint is public and
    # the key must never leave the server on a list call (PBI-040 scope).
    resp = httpx.get(MODELS_URL, timeout=_FETCH_TIMEOUT, headers={"Accept": "application/json"})
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise ValueError("unexpected OpenRouter models shape: missing data[]")
    rows = [_normalize_row(entry) for entry in data]
    return [r for r in rows if r.get("id")]


def _try_refresh() -> bool:
    """Attempt a live refresh; ``True`` on success, ``False`` on any failure.

    Never raises — a failure keeps the last good cache intact.
    """
    try:
        rows = _fetch_live()
    except Exception:
        return False
    _cache["models"] = rows
    _cache["by_id"] = {r["id"]: r for r in rows}
    _cache["fetched_at"] = _now()
    return True


def get_status() -> dict[str, Any]:
    """Cache health for responses and the write path (never fetches)."""
    has = _has_cache()
    fresh = _is_fresh() if has else False
    return {
        "cached": has,
        # Stale = we have rows but they are older than the TTL.
        "stale": has and not fresh,
        # Unavailable = no rows at all (nothing to serve or verify against).
        "unavailable": not has,
        "fetched_at": _cache.get("fetched_at"),
    }


def list_models(query: Optional[str] = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return ``(models, status)``; never raises into a request.

    When there is no cache, one live fetch is attempted. A fetch failure with
    rows already cached serves the stale rows (``status["stale"]`` is True);
    with no rows, ``models`` is empty and ``status["unavailable"]`` is True.
    """
    if not _has_cache():
        _try_refresh()
    elif not _is_fresh():
        # Opportunistic refresh for reads; a failure keeps serving stale rows.
        _try_refresh()
    status = get_status()
    models = list(_cache.get("models") or [])
    if query and isinstance(query, str) and query.strip():
        needle = query.strip().lower()
        models = [m for m in models if needle in m["id"].lower() or needle in (m.get("name") or "").lower()]
    return models, status


def model_exists(model_id: str) -> bool:
    """Exact ID match against the last verified data (no fetch on failure).

    Read-path helper: when there is no cache it attempts one fetch, then
    answers from whatever is available. Write paths must use
    ``verify_for_write()`` instead so a stale cache never authorises a save.
    """
    if not isinstance(model_id, str) or not model_id.strip():
        return False
    if not _has_cache():
        _try_refresh()
    return model_id.strip() in (_cache.get("by_id") or {})


def get_model(model_id: str) -> Optional[dict[str, Any]]:
    """One normalized row by exact ID, or ``None`` (read path, never raises)."""
    if not isinstance(model_id, str) or not model_id.strip():
        return None
    if not _has_cache():
        _try_refresh()
    return (_cache.get("by_id") or {}).get(model_id.strip())


def closest(query: str, limit: int = 3) -> list[str]:
    """Closest catalog IDs for rejection messages (never raises)."""
    try:
        ids = [m["id"] for m in (_cache.get("models") or []) if m.get("id")]
        if not query or not ids:
            return []
        needle = query.strip()
        if not needle:
            return []
        lowered = needle.lower()
        # Prefer substring matches (e.g. "gemini" → gemini rows) — they read
        # better than pure edit-distance when the dead ID shares a family name.
        substring = [i for i in ids if lowered in i.lower()]
        # difflib catches the renamed-ID case
        # (``google/gemini-2.0-flash-001`` → ``google/gemini-3.5-flash-lite``).
        fuzzy = difflib.get_close_matches(needle, ids, n=limit, cutoff=0.4)
        ordered: list[str] = []
        for candidate in [*substring, *fuzzy]:
            if candidate not in ordered:
                ordered.append(candidate)
            if len(ordered) >= limit:
                break
        return ordered
    except Exception:
        return []


def verify_for_write(model_id: str) -> dict[str, Any]:
    """Validate ``model_id`` for a write; the stale-cache refinement rule lives here.

    - Fresh cache → validate against it.
    - No cache or stale cache → force a live refresh first.
    - Refresh failure → raise ``CatalogUnavailable`` (the write path refuses
      and says the catalog cannot be verified — it never accepts blindly),
      even when stale rows exist.
    - Unknown ID → raise ``LookupError`` carrying suggestions in ``args``.

    Returns the normalized row on success.
    """
    if not isinstance(model_id, str) or not model_id.strip():
        raise LookupError(model_id, [])
    candidate = model_id.strip()
    if not _has_cache() or not _is_fresh():
        if not _try_refresh():
            raise CatalogUnavailable(
                "OpenRouter model catalog cannot be verified right now; "
                "refusing to save an unverified model ID"
            )
    row = (_cache.get("by_id") or {}).get(candidate)
    if row is None:
        raise LookupError(candidate, closest(candidate))
    return row
