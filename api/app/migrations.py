"""Minimal SQL migration runner.

Applies ``api/migrations/*.sql`` in lexical order inside a transaction. The SQL
files are idempotent (``IF NOT EXISTS``). Alembic remains the declared tool for
future schema evolution; this bootstrap keeps the initial schema runnable
without extra scaffolding. Requires ``DATABASE_URL``.
"""

from __future__ import annotations

from pathlib import Path

from .db import get_engine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def apply_migrations() -> list[str]:
    applied: list[str] = []
    engine = get_engine()
    with engine.begin() as conn:
        for path in migration_files():
            # exec_driver_sql passes the file verbatim to the driver.
            # text() would misparse JSON `:false`/`:true` literals as
            # bind parameters ("A value is required for bind parameter
            # 'false'"). The SQL files contain no driver placeholders.
            conn.exec_driver_sql(path.read_text(encoding="utf-8"))
            applied.append(path.name)
    return applied


if __name__ == "__main__":  # pragma: no cover - manual/CI invocation
    for name in apply_migrations():
        print(f"applied {name}")
