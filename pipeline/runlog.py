"""Per-node run logs (spec C7).

Structured diagnostic rows ``(run_id, node, level, message, detail, ts)`` —
the "what happened during a run" surface, separate from the audit log ("who
changed what"; see spec Decisions — the two are never merged, and no audit
row is ever written from a log path).

Injection mirrors ``cost_engine``: the runner puts a logger at
``config["configurable"]["run_logger"]``; nodes fetch it with
:func:`get_logger` and log best-effort. No logger configured (unit tests,
parity harness) → :class:`NullLogger`, so logging can never break a run.

Retention: none beyond a documented read cap (``QUERY_LIMIT``) — logs are
diagnostic, not the audit trail. Redaction rides along every write path:
message and string detail values pass through ``prompts.redact_for_log``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Protocol

# Read cap for the API (diagnostic surface — no retention/rotation policy).
QUERY_LIMIT = 1000

DEBUG = "debug"
INFO = "info"
WARN = "warn"
ERROR = "error"

LEVELS = (DEBUG, INFO, WARN, ERROR)


@dataclass(frozen=True)
class LogRecord:
    run_id: str
    node: str
    level: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)
    ts: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redacted(record: LogRecord) -> LogRecord:
    """Mask secrets-looking text in message + string detail values."""
    from .prompts import redact_for_log

    detail = {
        key: redact_for_log(value) if isinstance(value, str) else value
        for key, value in (record.detail or {}).items()
    }
    return LogRecord(
        run_id=record.run_id,
        node=record.node,
        level=record.level,
        message=redact_for_log(record.message),
        detail=detail,
        ts=record.ts or _now_iso(),
    )


class RunLogger(Protocol):
    """What nodes need: append one redacted row, never raise."""

    def log(
        self,
        node: str,
        level: str,
        message: str,
        *,
        run_id: str = "",
        detail: Optional[dict[str, Any]] = None,
    ) -> Optional[LogRecord]: ...

    def info(self, node: str, message: str, *, run_id: str = "",
             detail: Optional[dict[str, Any]] = None) -> Optional[LogRecord]: ...

    def warn(self, node: str, message: str, *, run_id: str = "",
             detail: Optional[dict[str, Any]] = None) -> Optional[LogRecord]: ...

    def error(self, node: str, message: str, *, run_id: str = "",
              detail: Optional[dict[str, Any]] = None) -> Optional[LogRecord]: ...


class _BaseLogger:
    """Shared convenience methods; subclasses implement ``log``."""

    def info(self, node: str, message: str, *, run_id: str = "",
             detail: Optional[dict[str, Any]] = None) -> Optional[LogRecord]:
        return self.log(node, INFO, message, run_id=run_id, detail=detail)

    def warn(self, node: str, message: str, *, run_id: str = "",
             detail: Optional[dict[str, Any]] = None) -> Optional[LogRecord]:
        return self.log(node, WARN, message, run_id=run_id, detail=detail)

    def error(self, node: str, message: str, *, run_id: str = "",
              detail: Optional[dict[str, Any]] = None) -> Optional[LogRecord]:
        return self.log(node, ERROR, message, run_id=run_id, detail=detail)


class NullLogger(_BaseLogger):
    """Default when no logger is configured — drops everything, never raises."""

    def log(self, node: str, level: str, message: str, *, run_id: str = "",
            detail: Optional[dict[str, Any]] = None) -> None:
        return None


NULL_LOGGER = NullLogger()


class MemoryRunLogger(_BaseLogger):
    """In-memory logger for tests and offline runs (redaction still applied)."""

    def __init__(self) -> None:
        self.rows: list[LogRecord] = []

    def log(self, node: str, level: str, message: str, *, run_id: str = "",
            detail: Optional[dict[str, Any]] = None) -> LogRecord:
        record = _redacted(LogRecord(
            run_id=run_id, node=node, level=level, message=message,
            detail=dict(detail or {}), ts=_now_iso(),
        ))
        self.rows.append(record)
        return record

    def for_node(self, node: str) -> list[LogRecord]:
        return [row for row in self.rows if row.node == node]

    def clear(self) -> None:
        self.rows.clear()


class SqlRunLogger(_BaseLogger):
    """Postgres-backed logger for production runs (best-effort, never raises).

    ``publish`` optionally fans each row out as a ``run.log`` SSE event —
    best-effort too (a slow broker never blocks the graph).
    """

    def __init__(self, engine: Any, run_id: str,
                 publish: Optional[Callable[[dict[str, Any]], Any]] = None) -> None:
        self._engine = engine
        self._run_id = run_id
        self._publish = publish

    def log(self, node: str, level: str, message: str, *, run_id: str = "",
            detail: Optional[dict[str, Any]] = None) -> Optional[LogRecord]:
        record = _redacted(LogRecord(
            run_id=run_id or self._run_id, node=node, level=level,
            message=message, detail=dict(detail or {}), ts=_now_iso(),
        ))
        try:
            import json

            from sqlalchemy import text

            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO run_logs (run_id, node, level, message, detail_json) "
                        "VALUES (:run_id, :node, :level, :message, "
                        "CAST(:detail AS jsonb))"
                    ),
                    {
                        "run_id": record.run_id,
                        "node": record.node,
                        "level": record.level,
                        "message": record.message,
                        "detail": json.dumps(record.detail),
                    },
                )
        except Exception:
            return None  # logging must never break a run
        if self._publish is not None:
            try:
                self._publish({
                    "type": "run.log",
                    "run_id": record.run_id,
                    "node": record.node,
                    "level": record.level,
                    "message": record.message,
                    "ts": record.ts,
                })
            except Exception:
                pass  # slow broker never blocks the graph
        return record


def get_logger(configurable: Optional[dict[str, Any]]) -> RunLogger:
    """The run's logger from ``config['configurable']`` (NullLogger when absent).

    Never raises and never returns None — call sites stay unconditional.
    """
    try:
        candidate = (configurable or {}).get("run_logger")
        if candidate is not None and hasattr(candidate, "log"):
            return candidate
    except Exception:
        pass
    return NULL_LOGGER
