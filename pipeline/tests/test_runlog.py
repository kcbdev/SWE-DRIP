"""Per-node run logs (PBI-042, spec C7).

Logging is best-effort and redacted: a broken store never breaks a run, and
token-looking text never lands in a row. Nodes stay unconditional — with no
logger configured they get the NullLogger.
"""

from __future__ import annotations

import json
from typing import Any

from pipeline import runlog
from pipeline.nodes.trend import trend_research
from pipeline.runlog import (
    MemoryRunLogger,
    NullLogger,
    SqlRunLogger,
    get_logger,
)


class _ChatStub:
    def __init__(self, content: str) -> None:
        self.content = content
        self.raw: dict[str, Any] = {"usage": {}}
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> "_ChatStub":
        self.calls.append(kwargs)
        return self


BRIEFS = [
    {"id": "b1", "subject": "Vibe", "text": "tee", "style": "mono-log",
     "engagement": 35, "novelty": 20, "specificity": 15},
    {"id": "b2", "subject": "Merge", "text": "tee", "style": "mono-log",
     "engagement": 30, "novelty": 25, "specificity": 20},
]


class TestLoggerSelection:
    def test_absent_logger_is_null_and_silent(self) -> None:
        logger = get_logger({})
        assert isinstance(logger, NullLogger)
        assert logger.info("trend_research", "hello", run_id="r") is None

    def test_malformed_config_never_raises(self) -> None:
        assert isinstance(get_logger(None), NullLogger)
        assert isinstance(get_logger({"run_logger": object()}), NullLogger)

    def test_memory_logger_records_rows(self) -> None:
        logger = MemoryRunLogger()
        row = logger.info("copy", "writing", run_id="run-1", detail={"model": "m"})
        assert row is not None and row.run_id == "run-1"
        assert logger.for_node("copy") == [row]
        assert logger.for_node("other") == []


class TestRedaction:
    def test_token_looking_text_is_masked(self) -> None:
        candidate = "sk" + "-or-" + "testkey123abc"
        logger = MemoryRunLogger()
        row = logger.info("copy", f"using key {candidate}", run_id="r",
                          detail={"note": f"api_key={candidate}"})
        assert row is not None
        assert "testkey123abc" not in row.message
        assert "testkey123abc" not in json.dumps(row.detail)
        assert "[REDACTED-OPENROUTER-KEY]" in row.message

    def test_plain_text_untouched(self) -> None:
        logger = MemoryRunLogger()
        row = logger.info("shelf", "accepted tee at $32", run_id="r")
        assert row is not None and row.message == "accepted tee at $32"


class TestSqlLoggerBestEffort:
    def test_broken_engine_never_raises(self) -> None:
        class Broken:
            def begin(self):
                raise RuntimeError("db is gone")

        logger = SqlRunLogger(Broken(), "run-9")
        assert logger.info("shelf", "accepted", run_id="run-9") is None

    def test_publish_failure_never_raises(self) -> None:
        rows: list[dict[str, Any]] = []

        class FakeConn:
            def execute(self, *args: Any, **kwargs: Any) -> None:
                rows.append({})

            def __enter__(self) -> "FakeConn":
                return self

            def __exit__(self, *args: Any) -> None:
                return None

        class FakeEngine:
            def begin(self) -> FakeConn:
                return FakeConn()

        def boom(event: dict[str, Any]) -> None:
            raise RuntimeError("broker is gone")

        logger = SqlRunLogger(FakeEngine(), "run-9", publish=boom)
        assert logger.info("shelf", "accepted", run_id="run-9") is not None
        assert len(rows) == 1


class _FakeEngine:
    class _Conn:
        def execute(self, *args: Any, **kwargs: Any) -> None:
            return None

        def __enter__(self) -> "_FakeEngine._Conn":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    def begin(self) -> "_FakeEngine._Conn":
        return self._Conn()


class TestNodeEmission:
    def test_trend_emits_start_model_and_done_rows(self) -> None:
        logger = MemoryRunLogger()
        stub = _ChatStub(json.dumps({"clusters": [{"theme": "V", "brief_ids": ["b1", "b2"]}]}))
        out = trend_research(
            {"briefs": BRIEFS},  # type: ignore[dict-item]
            {"configurable": {"llm_client": stub, "thread_id": "run-1",
                              "cost_engine": _FakeEngine(),
                              "run_logger": logger}},  # type: ignore[typeddict-item]
        )
        assert len(out["clusters"]) == 1
        rows = logger.for_node("trend_research")
        assert any("clustering 2 briefs" in r.message for r in rows)
        assert any("1 clusters" in r.message for r in rows)

    def test_failed_node_log_names_the_reason(self) -> None:
        logger = MemoryRunLogger()
        out = trend_research(
            {"briefs": []},  # type: ignore[dict-item]
            {"configurable": {"thread_id": "run-1", "run_logger": logger}},  # type: ignore[typeddict-item]
        )
        assert out["clusters"] == []
        rows = logger.for_node("trend_research")
        assert any("none passing" in r.message for r in rows)

    def test_no_logger_configured_still_runs(self) -> None:
        stub = _ChatStub(json.dumps({"clusters": [{"theme": "V", "brief_ids": ["b1", "b2"]}]}))
        out = trend_research(
            {"briefs": BRIEFS},  # type: ignore[dict-item]
            {"configurable": {"llm_client": stub}},  # type: ignore[typeddict-item]
        )
        assert len(out["clusters"]) == 1


class TestQueryCap:
    def test_cap_is_documented_and_bounded(self) -> None:
        assert runlog.QUERY_LIMIT == 1000

    def test_migration_carries_the_logged_columns(self) -> None:
        # Guards drift between runlog.py's INSERT and api/migrations/0006_run_logs.sql.
        from pathlib import Path

        sql = (Path(__file__).resolve().parents[2] / "api" / "migrations"
               / "0006_run_logs.sql").read_text(encoding="utf-8")
        for column in ("run_id", "node", "level", "message", "detail_json", "created_at"):
            assert column in sql
