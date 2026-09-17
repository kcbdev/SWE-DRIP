"""Brand style repository loader (spec C1, PBI-048).

The 7 locked graphic languages live in the styles repo (``styles.yaml``
under the collections root) — agents read through this module, never
hardcoded names. A missing or malformed repo file is loud (no silent
fallback vocabulary: inventing styles would be fabrication). Management
(create/edit) is founder-gated: the PBI-056 API or this file, both
audited; the loader only reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_FILENAME = "styles.yaml"


def repo_path(root: Path | str | None = None) -> Path:
    """Resolve the styles repo file.

    Explicit ``root`` keeps the legacy layout (the collections dir under
    ``<root>``); otherwise the env-driven collections root (PBI-053) so a volume-mounted
    repo is found in production and the repo-relative default locally.
    """
    if root is not None:
        return Path(root) / "collections" / REPO_FILENAME
    from .paths import collections_root

    return collections_root() / REPO_FILENAME


def load_styles(root: Path | str | None = None) -> dict[str, Any]:
    """Load and validate the styles repo; loud on any problem."""
    path = repo_path(root)
    if not path.is_file():
        raise FileNotFoundError(f"style repository not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"style repository is not valid YAML: {exc}") from None
    if not isinstance(raw, dict) or not isinstance(raw.get("styles"), list):
        raise ValueError("style repository must map to a 'styles' list")
    if "version" not in raw:
        raise ValueError("style repository must carry a 'version'")
    names: list[str] = []
    for entry in raw["styles"]:
        if not isinstance(entry, dict):
            raise ValueError(f"style entry must be a mapping: {entry!r}")
        name = entry.get("name")
        definition = entry.get("graphic_definition")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"style entry needs a non-empty name: {entry!r}")
        if not isinstance(definition, str) or not definition.strip():
            raise ValueError(f"style {name!r} needs a non-empty graphic_definition")
        if name in names:
            raise ValueError(f"duplicate style name: {name!r}")
        names.append(name)
    return {"version": raw.get("version", 1), "styles": raw["styles"]}


def style_names(root: Path | str | None = None) -> list[str]:
    """Locked style names in repo order."""
    return [s["name"] for s in load_styles(root)["styles"]]


def get_style(name: str, root: Path | str | None = None) -> dict[str, Any]:
    """One style entry by exact name; KeyError when unknown."""
    for entry in load_styles(root)["styles"]:
        if entry["name"] == name:
            return dict(entry)
    raise KeyError(f"unknown brand style: {name!r}")


def assert_known_archetype(style_archetype: Any, root: Path | str | None = None) -> str:
    """Validate an archetype against the repo; loud with the locked list."""
    names = style_names(root)
    if style_archetype not in names:
        raise ValueError(f"unknown style_archetype {style_archetype!r} (locked: {names!r})")
    return style_archetype
