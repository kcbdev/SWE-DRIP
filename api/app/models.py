"""Shared SQLAlchemy table definitions.

The audit log is append-only by construction (spec C1): there is no UPDATE or
DELETE path for ``audit_log`` anywhere in the codebase.
"""

from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Column, DateTime, Index, MetaData, String, Table, func

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
