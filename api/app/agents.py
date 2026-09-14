"""Agent roster assembly (FR-17, C4).

Builds per-node info from the single routing table, budget caps in the
settings store, and month-to-date spend rolled up from ``model_calls``.

Budget caps live in settings under the key ``agent_budget_caps`` as
``{node: cap_usd}``.  The default is ``50.0`` per node per month.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .settings_store import get_setting, set_setting

# Default monthly budget cap per node (USD).
_DEFAULT_CAP = 50.0

# Global monthly budget ceiling (AGENTS.md §3, $130/mo).
GLOBAL_MONTHLY_CAP = 130.0


@dataclass(frozen=True)
class AgentInfo:
    node: str
    role: str
    model: str | None
    cap_usd: float
    spend_usd: float


def _spend_by_node() -> dict[str, float]:
    """Roll up month-to-date spend from ``model_calls`` per node."""
    from sqlalchemy import text

    from .db import get_engine

    engine = get_engine()
    now = datetime.now(timezone.utc)
    year_month = now.strftime("%Y-%m")

    try:
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT node, COALESCE(SUM(cost_usd), 0) AS total "
                        "FROM model_calls "
                        "WHERE to_char(created_at, 'YYYY-MM') = :ym "
                        "GROUP BY node"
                    ),
                    {"ym": year_month},
                )
                .mappings()
                .all()
            )
        return {row["node"]: float(row["total"]) for row in rows}
    except Exception:
        return {}


def get_budget_caps() -> dict[str, float]:
    """Return per-node budget caps from the settings store."""
    raw = get_setting("agent_budget_caps", {})
    return {k: float(v) for k, v in raw.items()}


def set_budget_cap(node: str, cap_usd: float) -> dict[str, float]:
    """Set a single node's budget cap and persist."""
    caps = get_budget_caps()
    caps[node] = cap_usd
    set_setting("agent_budget_caps", caps)
    return caps


def get_roster() -> list[AgentInfo]:
    """Build the full agent roster."""
    from pipeline.routing import MODEL_FOR_NODE, NODE_ORDER

    caps = get_budget_caps()
    spend = _spend_by_node()

    agents = []
    for node in NODE_ORDER:
        model = MODEL_FOR_NODE.get(node)
        role = _role_for_node(node, model)
        agents.append(
            AgentInfo(
                node=node,
                role=role,
                model=model,
                cap_usd=caps.get(node, _DEFAULT_CAP),
                spend_usd=spend.get(node, 0.0),
            )
        )
    return agents


def get_agent_detail(node: str) -> AgentInfo | None:
    """Return info for a single node, or None if unknown."""
    roster = get_roster()
    for agent in roster:
        if agent.node == node:
            return agent
    return None


def _role_for_node(node: str, model: str | None) -> str:
    """Human-readable role label for a pipeline node."""
    roles = {
        "trend_research": "Trend Research",
        "contract_approval": "Contract Approval",
        "listing_copy": "Listing Copy",
        "design_spec": "Design Spec",
        "art_render": "Art Render",
        "placement": "Placement",
        "aesthetic_qc": "Aesthetic QC",
        "technical_qc": "Technical QC",
        "fw_create": "FW Create",
        "publish_gate": "Publish Gate",
        "shelf": "Shelf",
    }
    return roles.get(node, node)
