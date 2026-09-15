"""Database access for the Control Panel API.

Engines are created lazily and never at import time, so the API (and its tests)
run fully offline without ``DATABASE_URL``.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from .config import settings


def normalize_database_url(url: str) -> str:
    """Normalize a Postgres URL to the ``postgresql+psycopg`` dialect.

    The runtime dependency is ``psycopg`` v3 (not ``psycopg2``), so the bare
    ``postgresql://`` scheme — and the ``postgres://`` alias emitted by
    Coolify/Heroku-style platforms — would fail at engine creation with
    ``ModuleNotFoundError: No module named 'psycopg2'``. Non-Postgres URLs
    (e.g. SQLite in tests) pass through untouched.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine.

    Raises ``RuntimeError`` when ``DATABASE_URL`` is not configured. Callers that
    genuinely need the database should treat that as a configuration error;
    unit-level gates never reach this path.
    """
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return create_engine(normalize_database_url(settings.database_url), pool_pre_ping=True, future=True)
