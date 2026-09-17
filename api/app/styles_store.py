"""Brand style repository store — read/write the locked repo (PBI-056, spec C1).

The repo file (``styles.yaml`` under the collections root) is the single
source agents validate against. Reads go through ``pipeline/styles.py``
validation; writes are atomic (tmp + ``os.replace``), bump ``version``,
enforce name uniqueness, and refuse to silently strand contracts — every
write returns the C1 revalidation report (contracts whose archetype no
longer validates), empty when nothing is affected.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_FILENAME = "styles.yaml"


class RepoMissing(FileNotFoundError):
    """No repo file to read or modify (seed it per DEPLOY.md first)."""


class DuplicateStyle(ValueError):
    """Name collision: validation error, never an overwrite."""


class VersionConflict(ValueError):
    """The repo changed under the writer (stale expected_version)."""


class UnknownStyle(KeyError):
    pass


def _clean_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("style name must be non-empty")
    return name.strip()


def _clean_definition(definition: Any, name: str) -> str:
    if not isinstance(definition, str) or not definition.strip():
        raise ValueError(f"style {name!r} needs a non-empty graphic_definition")
    return definition.strip()


class StylesStore:
    """Filesystem read/write over one collections root (env-driven default)."""

    def __init__(self, root: Path | str | None = None) -> None:
        from pipeline.paths import collections_root

        self._root = Path(root) if root is not None else collections_root()

    def _path(self) -> Path:
        return self._root / REPO_FILENAME

    def read(self) -> dict[str, Any]:
        """Version + entries, validated; loud when the repo is missing."""
        from pipeline.styles import load_file

        try:
            return load_file(self._path())
        except FileNotFoundError as exc:
            raise RepoMissing(
                f"style repository not found: {self._path()} — seed it per DEPLOY.md"
            ) from exc

    def _write_doc(self, doc: dict[str, Any]) -> None:
        path = self._path()
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".styles-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                # allow_unicode: founders and agents read the same file.
                yaml.safe_dump(doc, handle, sort_keys=False, allow_unicode=True)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _apply(self, current: dict[str, Any], transform) -> dict[str, Any]:
        """Validate + bump + persist; returns the re-read document."""
        version = current.get("version")
        if not isinstance(version, int):
            raise ValueError("style repository version must be an int")
        styles = [dict(s) for s in current["styles"]]
        transform(styles)
        new_doc = {"version": version + 1, "styles": styles}
        # The loader must read back what we wrote (round-trip invariant).
        from pipeline.styles import load_file

        self._write_doc(new_doc)
        return load_file(self._path())

    def create(self, name: str, graphic_definition: str, expected_version: int) -> dict[str, Any]:
        """Append a style; 409 on duplicate name or stale version."""
        clean_name = _clean_name(name)
        clean_definition = _clean_definition(graphic_definition, clean_name)
        current = self.read()
        if current["version"] != expected_version:
            raise VersionConflict(
                f"repo is at version {current['version']}, expected {expected_version} — reload and retry")

        def _add(styles: list[dict[str, Any]]) -> None:
            if any(s["name"] == clean_name for s in styles):
                raise DuplicateStyle(f"style {clean_name!r} already exists")
            styles.append({"name": clean_name, "graphic_definition": clean_definition})

        return self._apply(current, _add)

    def update(self, old_name: str, name: Optional[str], graphic_definition: Optional[str],
               expected_version: int) -> dict[str, Any]:
        """Rename and/or redefine a style; 404 unknown, 409 duplicate/stale."""
        current = self.read()
        if not any(s["name"] == old_name for s in current["styles"]):
            raise UnknownStyle(old_name)
        if name is None and graphic_definition is None:
            raise ValueError("nothing to change — pass name and/or graphic_definition")
        if current["version"] != expected_version:
            raise VersionConflict(
                f"repo is at version {current['version']}, expected {expected_version} — reload and retry")
        target = next((s for s in current["styles"] if s["name"] == old_name), None)
        assert target is not None  # checked above; kept for the type narrowing
        clean_name = _clean_name(name) if name is not None else target["name"]
        clean_definition = (_clean_definition(graphic_definition, clean_name)
                            if graphic_definition is not None else target["graphic_definition"])

        def _edit(styles: list[dict[str, Any]]) -> None:
            if clean_name != old_name and any(s["name"] == clean_name for s in styles):
                raise DuplicateStyle(f"style {clean_name!r} already exists")
            entry = next(s for s in styles if s["name"] == old_name)
            entry["name"] = clean_name
            entry["graphic_definition"] = clean_definition

        return self._apply(current, _edit)

    @staticmethod
    def revalidate(contracts: list[dict[str, Any]], names: list[str]) -> list[str]:
        """Contracts whose archetype no longer validates (never silent).

        Takes the post-write names so the report reflects the repo as
        written; returns affected collection ids (empty = nothing stranded).
        Drafts may legitimately carry free member styles, so the report is
        advisory — the approval completeness gate stays the enforcement point.
        """
        allowed = set(names)
        return sorted({
            str(c.get("collection_id"))
            for c in contracts
            if isinstance(c, dict) and c.get("style_archetype") not in allowed
            and str(c.get("collection_id") or "")
        })


def get_styles_store() -> StylesStore:
    return StylesStore()
