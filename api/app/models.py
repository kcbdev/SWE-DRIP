"""Shared SQLAlchemy table definitions.

The audit log is append-only by construction (spec C1): there is no UPDATE or
DELETE path for ``audit_log`` anywhere in the codebase.
"""

from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Column, DateTime, Index, MetaData, String, Table, Text, func, text

metadata = MetaData()

audit_log = Table(
    "audit_log",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("actor_user_id", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("action", String(64), nullable=False),
    Column("entity_type", String(64), nullable=False),
    Column("entity_id", String(128), nullable=True),
    Column("before_json", JSON, nullable=True),
    Column("after_json", JSON, nullable=True),
    Index("ix_audit_log_actor", "actor_user_id"),
    Index("ix_audit_log_action", "action"),
    Index("ix_audit_log_entity", "entity_type", "entity_id"),
    Index("ix_audit_log_created", "created_at"),
)

# Approvals index (data spec §1.2; migration 0003). Query/filter rows only —
# gate state itself lives in LangGraph interrupts (spec Decisions, NFR-1).
hitl_approvals = Table(
    "hitl_approvals",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("run_id", String(128), nullable=False),
    Column("node", String(64), nullable=False),
    Column("status", String(32), nullable=False, default="pending"),
    Column("reviewer_user_id", String(128), nullable=True),
    Column("note", Text, nullable=True),
    Column("decided_at", DateTime(timezone=True), nullable=True),
    Index("ix_hitl_approvals_status", "status"),
    Index("ix_hitl_approvals_run", "run_id"),
    # Mirrors migration 0003's partial unique index: exactly one open row per
    # gate, so create_all deployments enforce what the SQL already forbids.
    Index(
        "uq_hitl_approvals_open",
        "run_id",
        "node",
        unique=True,
        postgresql_where=text("status = 'pending'"),
    ),
)
