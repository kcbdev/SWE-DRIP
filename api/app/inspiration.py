"""Inspiration assets per collection draft (spec C3, PBI-049).

Operator-curated visual research lives beside the contract it informs:
``{COLLECTIONS_DIR}/<slug>.assets/{uuid}.{ext}`` plus a provenance sidecar
``{uuid}.json`` (source URL or "upload", note, actor, timestamp). Link
references (no bytes) append to the contract's ``inspiration_refs`` through
the normal validated update path.

Loudness over convenience: non-images, oversize payloads, and path
traversal are rejected, never normalized. The bytes on disk are the truth;
sidecars index them (an asset without a sidecar is invisible, never
guessed).
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .collections_store import (
    CollectionNotFound,
    CollectionsStore,
    DEFAULT_COLLECTIONS_DIR,
    MtimeConflict,
)

MAX_BYTES = 5 * 1024 * 1024

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"

_ALLOWED_TYPES = {"image/png": ".png", "image/jpeg": ".jpg"}

_ASSET_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def resolve_collections_root() -> Path:
    """Collections root: env-driven with a repo-relative default (PBI-053
    mounts the volume; this helper is the single place the path resolves)."""
    override = os.environ.get("SWE_DRIP_COLLECTIONS_DIR")
    return Path(override) if override else DEFAULT_COLLECTIONS_DIR


def _slug_dir(root: Path, slug: str) -> Path:
    if not slug or "/" in slug or "\\" in slug or slug.startswith("."):
        raise ValueError(f"invalid slug {slug!r}")
    return root / f"{slug}.assets"


def _check_asset_id(asset_id: str) -> str:
    if not isinstance(asset_id, str) or not _ASSET_ID.match(asset_id):
        raise ValueError(f"invalid asset id {asset_id!r}")
    return asset_id


def sniff_image(content: bytes, declared: str) -> str:
    """Return the extension for validated image bytes; loud otherwise."""
    if declared not in _ALLOWED_TYPES:
        raise ValueError(f"unsupported content type {declared!r} (PNG/JPEG only)")
    if len(content) > MAX_BYTES:
        raise ValueError(f"image exceeds {MAX_BYTES} bytes")
    if content.startswith(PNG_MAGIC):
        ext = ".png"
    elif content.startswith(JPEG_MAGIC):
        ext = ".jpg"
    else:
        raise ValueError("bytes are not a PNG or JPEG image (bad magic)")
    if _ALLOWED_TYPES[declared] != ext:
        raise ValueError(f"content type {declared!r} does not match image bytes")
    return ext


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class InspirationStore:
    """Filesystem asset store bound to one collections root."""

    def __init__(self, root: Path | str | None = None,
                 collections: Optional[CollectionsStore] = None) -> None:
        self._root = Path(root) if root is not None else resolve_collections_root()
        self._collections = collections

    def _store(self) -> CollectionsStore:
        return self._collections or CollectionsStore(self._root)

    def _require_collection(self, slug: str) -> None:
        try:
            self._store().get(slug)
        except CollectionNotFound:
            raise
        except Exception as exc:
            raise ValueError(f"cannot read collection {slug!r}: {exc}") from exc

    def add_asset(
        self,
        slug: str,
        content: bytes,
        declared_type: str,
        *,
        note: str = "",
        source_url: str = "",
        actor_user_id: str,
    ) -> dict[str, Any]:
        """Store validated image bytes + sidecar; returns the asset record."""
        self._require_collection(slug)
        if not actor_user_id:
            raise ValueError("actor_user_id is required")
        if source_url:
            lowered_source = source_url.strip().lower()
            if not (lowered_source.startswith("http://")
                    or lowered_source.startswith("https://")):
                raise ValueError(f"source_url must be http(s) or empty, got {source_url!r}")
        ext = sniff_image(content, declared_type)
        asset_id = uuid.uuid4().hex
        directory = _slug_dir(self._root, slug)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{asset_id}{ext}").write_bytes(content)
        record = {
            "id": asset_id,
            "filename": f"{asset_id}{ext}",
            "content_type": "image/png" if ext == ".png" else "image/jpeg",
            "size_bytes": len(content),
            "source_url": source_url,
            "note": note,
            "actor_user_id": actor_user_id,
            "created_at": _utcnow(),
        }
        (directory / f"{asset_id}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8")
        return record

    def add_link(self, slug: str, url: str, note: str = "") -> dict[str, Any]:
        """Append a link reference to the contract (validated update path)."""
        if not isinstance(url, str) or not url.strip():
            raise ValueError("link url is required")
        lowered = url.strip().lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            raise ValueError(f"link url must be http(s), got {url!r}")
        store = self._store()
        record = store.get(slug)  # raises CollectionNotFound
        refs = list(record["contract"].get("inspiration_refs") or [])
        entry = {"url": url.strip(), "note": note}
        refs.append(entry)
        # Lost-update guard: concurrent appends retry once on mtime conflict.
        try:
            store.update(slug, {"inspiration_refs": refs},
                         expected_mtime=record["mtime"])
        except MtimeConflict:
            fresh = store.get(slug)
            refs = list(fresh["contract"].get("inspiration_refs") or [])
            refs.append(entry)
            store.update(slug, {"inspiration_refs": refs},
                         expected_mtime=fresh["mtime"])
        return entry

    def list(self, slug: str) -> dict[str, Any]:
        """Assets (sidecar-indexed) + contract link refs for one collection."""
        self._require_collection(slug)
        directory = _slug_dir(self._root, slug)
        assets = []
        if directory.is_dir():
            for sidecar in sorted(directory.glob("*.json")):
                try:
                    record = json.loads(sidecar.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue  # unreadable sidecar: invisible, never guessed
                if not isinstance(record, dict) or "id" not in record:
                    continue
                if not (directory / str(record.get("filename", ""))).is_file():
                    continue  # bytes gone: not listed
                assets.append(record)
        refs = self._store().get(slug)["contract"].get("inspiration_refs") or []
        return {"assets": assets, "refs": list(refs)}

    def read_bytes(self, slug: str, asset_id: str) -> tuple[bytes, str]:
        """Raw bytes + content type for serving; traversal-safe by construction."""
        self._require_collection(slug)
        _check_asset_id(asset_id)
        directory = _slug_dir(self._root, slug)
        for ext in (".png", ".jpg"):
            candidate = directory / f"{asset_id}{ext}"
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved.parent != directory.resolve() or not resolved.is_file():
                continue
            return resolved.read_bytes(), "image/png" if ext == ".png" else "image/jpeg"
        raise CollectionNotFound(f"asset {asset_id!r} in {slug!r}")

    def delete(self, slug: str, asset_id: str) -> bool:
        """Remove bytes + sidecar; True when something was removed."""
        self._require_collection(slug)
        _check_asset_id(asset_id)
        directory = _slug_dir(self._root, slug)
        removed = False
        try:
            base = directory.resolve()
        except OSError:
            return False
        for name in (f"{asset_id}.png", f"{asset_id}.jpg", f"{asset_id}.json"):
            candidate = directory / name
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved.parent != base or not resolved.is_file():
                continue
            try:
                resolved.unlink()
                removed = True
            except OSError:
                continue
        return removed
