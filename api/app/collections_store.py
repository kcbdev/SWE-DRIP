"""YAML collection store — the ONLY filesystem writer for ``/collections``.

Contracts live only as ``/collections/<slug>.yaml`` (spec C1): schema-validated
on every read and write, atomic writes (tmp + ``os.replace``), mtime tracked
per contract so manual file edits are detectable — an update against a stale
mtime is rejected as a conflict, never silently authoritative. Postgres
indexes nothing beyond references (no contract content is stored in the DB).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import ValidationError

from .collections_schema import CollectionContract

DEFAULT_COLLECTIONS_DIR = Path(__file__).resolve().parent.parent.parent / "collections"


class CollectionNotFound(KeyError):
    pass


class CollectionExists(ValueError):
    """Slug collision: a validation error, never an overwrite."""


class MtimeConflict(ValueError):
    """The file changed under us (manual edit?) — refusing to clobber."""


# Non-contract YAML living beside contracts (never listed, never validated
# as a contract — listing validates every file it touches, so an
# unskipped reserved file is a 500 on GET /api/collections).
RESERVED_FILENAMES = frozenset({"styles.yaml"})


def contract_to_dict(contract: CollectionContract) -> dict[str, Any]:
    return contract.model_dump(mode="json")


class CollectionsStore:
    def __init__(self, root: Path | str = DEFAULT_COLLECTIONS_DIR) -> None:
        self._root = Path(root)

    # ------------------------------------------------------------------ read

    def list(self, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        """All schema-valid contracts (+ mtime), optionally filtered by status."""
        items = [self.get(path.stem) for path in sorted(self._path_glob())]
        if status is not None:
            items = [item for item in items if item["contract"]["status"] == status]
        return items

    def get(self, slug: str) -> dict[str, Any]:
        """One contract + mtime. Raises CollectionNotFound / ValidationError."""
        path = self._path(slug)
        if not path.is_file():
            raise CollectionNotFound(slug)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        contract = CollectionContract.model_validate(data)
        record = contract_to_dict(contract)
        record.setdefault("slug", slug)
        return {"contract": record, "mtime": path.stat().st_mtime}

    # ----------------------------------------------------------------- write

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate + atomically write a new contract. Slug collision errors."""
        contract = CollectionContract.model_validate(data)
        path = self._path(contract.collection_id)
        if path.exists():
            raise CollectionExists(f"slug {contract.collection_id!r} already exists")
        self._write_atomic(path, contract_to_dict(contract))
        return self.get(contract.collection_id)

    def update(
        self, slug: str, patch: dict[str, Any], *, expected_mtime: Optional[float] = None
    ) -> dict[str, Any]:
        """Merge a field patch onto the stored contract and rewrite atomically.

        ``collection_id`` is immutable; status transitions are the lifecycle's
        job (PBI-020) — this path rejects them. A stale ``expected_mtime``
        rejects the write as an MtimeConflict.
        """
        current = self.get(slug)  # validates + raises CollectionNotFound
        if expected_mtime is not None and current["mtime"] != expected_mtime:
            raise MtimeConflict(f"{slug!r} changed on disk (mtime mismatch)")
        merged = {**current["contract"]}
        merged.pop("slug", None)  # read-model alias, not a schema field
        if "collection_id" in patch and patch["collection_id"] != slug:
            raise ValueError(f"collection_id is immutable ({slug!r})")
        merged.update(patch)
        if merged.get("status") != current["contract"]["status"]:
            raise ValueError("status transitions go through the lifecycle endpoints (PBI-020)")
        contract = CollectionContract.model_validate(merged)
        self._write_atomic(self._path(slug), contract_to_dict(contract))
        return self.get(slug)

    def transition(
        self,
        slug: str,
        *,
        to_status: str,
        stamp: dict[str, Any],
        expected_mtime: Optional[float] = None,
    ) -> dict[str, Any]:
        """Lifecycle transition (approve/retire): atomic status + stamp write.

        The only path that may change ``status`` (PATCH rejects it). Validates
        the full contract after the merge; a stale ``expected_mtime`` rejects
        the write as an MtimeConflict (concurrent-edit guard, spec anti-pattern).
        """
        current = self.get(slug)  # validates + raises CollectionNotFound
        if expected_mtime is not None and current["mtime"] != expected_mtime:
            raise MtimeConflict(f"{slug!r} changed on disk (mtime mismatch)")
        merged = {**current["contract"]}
        merged.pop("slug", None)
        merged["status"] = to_status
        merged.update(stamp)
        contract = CollectionContract.model_validate(merged)
        self._write_atomic(self._path(slug), contract_to_dict(contract))
        return self.get(slug)

    # ---------------------------------------------------------------- helpers

    def _path(self, slug: str) -> Path:
        if not slug or "/" in slug or "\\" in slug or slug.startswith("."):
            raise ValueError(f"invalid slug {slug!r}")
        return self._root / f"{slug}.yaml"

    def _path_glob(self) -> list[Path]:
        if not self._root.is_dir():
            return []
        return [
            p for p in self._root.glob("*.yaml")
            if p.is_file() and p.name not in RESERVED_FILENAMES
        ]

    @staticmethod
    def _write_atomic(path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.stem, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.safe_dump(record, handle, sort_keys=False, allow_unicode=True)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def get_collections_store() -> CollectionsStore:
    return CollectionsStore()
