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


def setup_checkpointer() -> bool:
    """Create the LangGraph checkpointer tables (idempotent).

    The approvals/runs/designs readers scan ``checkpoints`` via
    ``PostgresSaver``; without ``setup()`` those pages 500 with
    ``UndefinedTable``. Uses the RAW ``DATABASE_URL`` (libpq accepts
    ``postgresql://``/``postgres://``; the ``+psycopg`` SQLAlchemy dialect
    suffix must NOT be passed here). No-op without ``DATABASE_URL`` so
    offline gates stay hermetic. Best-effort at startup: returns False
    (with the traceback printed) instead of taking the whole API down —
    the affected pages degrade while everything else keeps serving.
    """
    import os
    import traceback

    url = os.environ.get("DATABASE_URL")
    if not url:
        return True
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        saver = PostgresSaver.from_conn_string(url)
        if hasattr(saver, "__enter__"):
            with saver as opened:
                opened.setup()
        else:
            saver.setup()
    except Exception:
        print("checkpointer setup failed (approvals/runs will 500):")
        traceback.print_exc()
        return False
    print("checkpointer tables ready")
    return True


if __name__ == "__main__":  # pragma: no cover - manual/CI invocation
    for name in apply_migrations():
        print(f"applied {name}")
    setup_checkpointer()
