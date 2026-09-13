"""Checkpointer factory: MemorySaver by default, Postgres when configured.

Tests and offline gates always get ``MemorySaver`` (no DB, no network).
When ``DATABASE_URL`` is set, the factory returns the saver as an async
context manager — callers drive the graph with the async API::

    async with get_checkpointer() as saver:
        graph = build_graph(checkpointer=saver)
        await graph.ainvoke(...)

Divergence notes (PBI-010 refinement rule) vs the quickstart patterns, with
the installed ``langgraph-checkpoint-postgres 3.1.x``:
1. ``AsyncPostgresSaver`` lives at ``langgraph.checkpoint.postgres.aio`` —
   NOT at the top-level ``langgraph.checkpoint.postgres`` package.
2. ``AsyncPostgresSaver.from_conn_string`` returns an async context manager
   yielding the saver (it is NOT the saver instance itself).
"""

from __future__ import annotations

import os


def get_checkpointer():
    """Return a checkpointer without connecting (construction is offline-safe)."""
    if os.environ.get("DATABASE_URL"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        return AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URL"])
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
