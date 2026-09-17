"""Env-driven artifact roots (PBI-053, spec C3b).

Renders (`runs/`) and collection contracts + assets (`collections/`) must
survive redeploys: production mounts persistent volumes at these roots and
points the env vars below at the mount paths. Locally (and in every offline
gate) the vars are unset and the repo-relative defaults apply, so
`npm run verify` never needs Docker, volumes, or env configuration.

Single source: every flow — API starters, routers, pipeline nodes, the
styles loader — resolves through these two helpers. The grep-guard test
(`api/tests/test_storage_roots.py`) fails on hardcoded `runs/` /
`collections/` literals anywhere else.
"""

from __future__ import annotations

import os
from pathlib import Path

RUNS_DIR_ENV = "SWE_DRIP_RUNS_DIR"
COLLECTIONS_DIR_ENV = "SWE_DRIP_COLLECTIONS_DIR"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def runs_root() -> Path:
    """Render-artifact root: env override or repo-relative default."""
    override = os.environ.get(RUNS_DIR_ENV)
    return Path(override) if override else _repo_root() / "runs"


def collections_root() -> Path:
    """Collection contracts + assets root: env override or default."""
    override = os.environ.get(COLLECTIONS_DIR_ENV)
    return Path(override) if override else _repo_root() / "collections"
