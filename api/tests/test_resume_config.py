"""Resume must rebuild the runtime config the run started with.

Regression: `SyncGraphRunner.resume` used to pass ONLY `thread_id`, so resuming
any gate that is followed by a model-calling node died with
"no llm_client in config['configurable']" — i.e. approving a gate could never
progress a run in production, while every unit test passed because they inject
config directly. Found on the first real approve.
"""

from __future__ import annotations

from typing import Any

import pytest

from api.app.hitl import SyncGraphRunner


class _CapturingGraph:
    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values
        self.invoked: list[dict[str, Any]] = []

    def get_state(self, config: Any) -> Any:
        class _Snap:
            pass

        snap = _Snap()
        snap.values = self._values
        return snap

    def invoke(self, command: Any, config: Any) -> Any:
        self.invoked.append(config)
        return {}


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-used")
    import api.app.db as db

    monkeypatch.setattr(db, "get_engine", lambda: object())


def _patched(graph: _CapturingGraph) -> SyncGraphRunner:
    """A runner whose graph is the capturing fake (no real checkpointer needed)."""
    runner = SyncGraphRunner(saver_factory=lambda: object())
    runner._graph = lambda saver: graph  # type: ignore[method-assign]
    return runner


def test_resume_supplies_the_full_runtime_config() -> None:
    graph = _CapturingGraph(
        {
            "design_id": "d-7",
            "hitl": {"contract_approval": True},
            "node_config": {"trend_research": {"model": "frozen/model"}},
        }
    )
    _patched(graph).resume("thread-1", {"approved_cluster_id": "cluster-1"})

    configurable = graph.invoked[0]["configurable"]
    # Everything the nodes after the gate need to actually run.
    assert configurable["thread_id"] == "thread-1"
    assert configurable["llm_client"] is not None
    assert configurable["cost_engine"] is not None
    # Frozen per-run state is replayed, not re-resolved from today's settings.
    assert configurable["hitl"] == {"contract_approval": True}
    assert configurable["node_config"] == {"trend_research": {"model": "frozen/model"}}
    # Per-node logs must survive the resume: without a run_logger every node
    # after the first gate logs to the NullLogger and the run goes silent
    # mid-flight (found on the first MCP-driven live run).
    from pipeline.runlog import NullLogger

    assert configurable["run_logger"] is not None
    assert not isinstance(configurable["run_logger"], NullLogger)
    # Render artifacts land under the root the render endpoint serves from.
    assert configurable["run_dir"].endswith("runs\\d-7") or configurable["run_dir"].endswith(
        "runs/d-7"
    )


def test_resume_falls_back_to_current_hitl_for_older_runs() -> None:
    """A run started before flags were snapshotted still resumes."""
    graph = _CapturingGraph({"design_id": "d-8"})
    _patched(graph).resume("thread-2", {"approved": True})
    configurable = graph.invoked[0]["configurable"]
    assert configurable["hitl"]  # resolved from the settings store
    assert configurable["node_config"] == {}


def test_resume_uses_the_run_id_when_no_design_id() -> None:
    graph = _CapturingGraph({})
    _patched(graph).resume("thread-3", {"approved": True})
    assert "thread-3" in graph.invoked[0]["configurable"]["run_dir"]
