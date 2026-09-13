"""Cost logging to ``model_calls`` (spec C4).

Every model call logs ``{node, model, tokens_in, tokens_out, cost_usd}`` —
table owned by PBI-008 (``api/migrations/0002_model_calls.sql``), writer owned
here per the dashboard spec's sequencing note. The table is defined here with
SQLAlchemy (mirroring the migration) so the writer stays dependency-free of
the API package; callers pass an engine in (e.g. ``api.app.db.get_engine()``).

A logging failure is recorded and surfaced via :class:`CostOutcome` — never
silently swallowed, never crash-inducing: nodes attach the outcome to state
and the graph continues.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    func,
)
from sqlalchemy.engine import Engine

metadata = MetaData()

# Mirrors api/migrations/0002_model_calls.sql (append-only; no update/delete).
model_calls = Table(
    "model_calls",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("node", String(64), nullable=False),
    Column("model", String(128), nullable=False),
    Column("tokens_in", Integer, nullable=False, default=0),
    Column("tokens_out", Integer, nullable=False, default=0),
    Column("cost_usd", Numeric(12, 6), nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


@dataclass(frozen=True)
class CostRecord:
    node: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


@dataclass(frozen=True)
class CostOutcome:
    ok: bool
    error: str | None = None


def build_cost_record(
    node: str,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
) -> CostRecord:
    """Pure payload builder — the exact shape written per model call."""
    if not node or not model:
        raise ValueError("node and model are required on every cost record")
    return CostRecord(
        node=node,
        model=model,
        tokens_in=int(tokens_in or 0),
        tokens_out=int(tokens_out or 0),
        cost_usd=float(cost_usd or 0.0),
    )


def record_cost(record: CostRecord, engine: Engine) -> CostOutcome:
    """Insert one cost row; failures surface as ``CostOutcome`` (no raise)."""
    try:
        with engine.begin() as conn:
            conn.execute(
                model_calls.insert().values(
                    node=record.node,
                    model=record.model,
                    tokens_in=record.tokens_in,
                    tokens_out=record.tokens_out,
                    cost_usd=record.cost_usd,
                )
            )
    except Exception as exc:  # surfaced, never swallowed, never crash-inducing
        return CostOutcome(ok=False, error=f"{type(exc).__name__}: {exc}")
    return CostOutcome(ok=True)


def to_payload(record: CostRecord) -> dict[str, Any]:
    """JSON-able form of a cost record (dashboard rollups, audit)."""
    return {
        "node": record.node,
        "model": record.model,
        "tokens_in": record.tokens_in,
        "tokens_out": record.tokens_out,
        "cost_usd": record.cost_usd,
    }
