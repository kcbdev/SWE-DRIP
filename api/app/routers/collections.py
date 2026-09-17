"""Collections CRUD API (spec C1/C2/C5/C6).

YAML files are the single source (``CollectionsStore``); Postgres stores
nothing. Reads are Viewer+; create/edit are Admin-only. Status transitions
are the lifecycle's job (PBI-020) — PATCH rejects them. Every mutation writes
an audit row through the shared writer.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from ..audit import AuditWriter, get_audit_writer
from ..auth import ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, Actor
from ..collections_store import (
    CollectionExists,
    CollectionNotFound,
    CollectionsStore,
    MtimeConflict,
    get_collections_store,
)
from ..hitl import (
    HitlAmbiguous,
    HitlService,
    HitlStale,
    get_approval_index,
    get_gate_source,
    get_hitl_service,
)
from ..rbac import require_role

router = APIRouter(prefix="/api/collections", tags=["collections"])

ReadAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER))
AdminOnly = Depends(require_role(ROLE_ADMIN))
DecideAllowed = Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))

STATUSES = ("draft", "active", "retired")


def _detail(record: dict[str, Any]) -> dict[str, Any]:
    return {"id": record["contract"]["collection_id"], **record}


@router.get("")
def list_collections(
    actor: Actor = ReadAllowed,
    store: CollectionsStore = Depends(get_collections_store),
    status_filter: Optional[str] = Query(default=None, alias="status"),
) -> dict[str, Any]:
    if status_filter is not None and status_filter not in STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {STATUSES!r}")
    return {"items": [_detail(record) for record in store.list(status=status_filter)]}


@router.get("/rotation")
def get_rotation_queue(
    actor: Actor = ReadAllowed,
    store: CollectionsStore = Depends(get_collections_store),
) -> dict[str, Any]:
    """Rotation queue at a glance (Viewer+): next queued candidate + counts.

    Declared before ``/{slug}`` so "rotation" is never captured as a slug.
    The next candidate is the oldest draft by creation time — rotation never
    stalls waiting on research while a draft waits.
    """
    drafts = store.list(status="draft")
    actives = store.list(status="active")

    def _created(record: dict[str, Any]) -> str:
        return str(record["contract"].get("created_at") or "")

    ordered = sorted(drafts, key=_created)
    next_candidate = ordered[0]["contract"]["collection_id"] if ordered else None
    return {
        "next_candidate": next_candidate,
        "drafts": len(drafts),
        "actives": len(actives),
    }


@router.get("/{slug}")
def get_collection(
    slug: str,
    actor: Actor = ReadAllowed,
    store: CollectionsStore = Depends(get_collections_store),
) -> dict[str, Any]:
    try:
        return _detail(store.get(slug))
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")


@router.get("/{slug}/board/{ref:path}")
def get_board_file(
    slug: str,
    ref: str,
    actor: Actor = ReadAllowed,
    store: CollectionsStore = Depends(get_collections_store),
) -> Any:
    """Serve one mood-board image same-origin (Viewer+, PBI-055).

    Boards render into the collection's asset dir before any contract names
    them, so serving is scoped to the dir (relative-ref validation +
    traversal guard + image-suffix gate), not to the contract's ref list.
    """
    from fastapi.responses import Response

    from ..research_runs import serve_board_file

    try:
        store.get(slug)
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    try:
        content, media_type = serve_board_file(slug, ref)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown board ref")
    return Response(content=content, media_type=media_type)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: dict[str, Any],
    actor: Actor = AdminOnly,
    store: CollectionsStore = Depends(get_collections_store),
    writer: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    payload = {**payload, "status": "draft"}  # creates are always drafts
    try:
        record = store.create(payload)
    except CollectionExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_errors(exc))
    writer.record(
        actor_user_id=actor.user_id,
        action="collection.create",
        entity_type="collection",
        entity_id=record["contract"]["collection_id"],
        before=None,
        after=record["contract"],
    )
    return _detail(record)


@router.patch("/{slug}")
def update_collection(
    slug: str,
    payload: dict[str, Any],
    actor: Actor = AdminOnly,
    store: CollectionsStore = Depends(get_collections_store),
    writer: AuditWriter = Depends(get_audit_writer),
    expected_mtime: Optional[float] = Query(default=None),
) -> dict[str, Any]:
    try:
        before = store.get(slug)["contract"]
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    try:
        record = store.update(slug, payload, expected_mtime=expected_mtime)
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    except MtimeConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=_errors(exc))
    writer.record(
        actor_user_id=actor.user_id,
        action="collection.update",
        entity_type="collection",
        entity_id=slug,
        before=before,
        after=record["contract"],
    )
    return _detail(record)


def _errors(exc: BaseException) -> list[dict[str, Any]]:
    if isinstance(exc, ValidationError):
        return exc.errors(include_url=False)
    return [{"type": "value_error", "loc": (), "msg": str(exc)}]


# ------------------------------------------------------------- lifecycle (PBI-020)


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _completeness_errors(contract: dict[str, Any]) -> list[str]:
    """Value-completeness gate at approve time: filled palette + thresholds."""
    errors: list[str] = []
    if not ((contract.get("illustration_rules") or {}).get("palette")):
        errors.append("illustration_rules.palette must be filled before approval")
    thresholds = contract.get("kpi_thresholds") or {}
    for key in ("min_units", "min_conversion", "eval_window_days"):
        if thresholds.get(key) is None:
            errors.append(f"kpi_thresholds.{key} must be set before approval")
    # Locked style vocabulary (collection-research C1): drafts may carry free
    # member styles, but approval locks one of the 7 brand styles. A missing
    # repo file is a completeness failure (422), never a 500.
    try:
        from pipeline.styles import assert_known_archetype

        assert_known_archetype(contract.get("style_archetype"))
    except (ValueError, KeyError, OSError) as exc:
        errors.append(f"style_archetype must be a locked brand style before approval: {exc}")
    return errors


@router.post("/candidates", status_code=status.HTTP_201_CREATED)
def create_candidate(
    payload: dict[str, Any],
    actor: Actor = AdminOnly,
    store: CollectionsStore = Depends(get_collections_store),
    writer: AuditWriter = Depends(get_audit_writer),
) -> dict[str, Any]:
    """Surface Trend-cluster output as a draft candidate (spec C3).

    Body: ``{"cluster": {"cluster_id", "theme", "brief_ids"}, "member_styles": [...]}``.
    Drafting reuses the pipeline contract builder verbatim (no second mapping).
    """
    from pipeline.nodes.contract import draft_contract

    cluster = payload.get("cluster")
    member_styles = payload.get("member_styles")
    if not isinstance(cluster, dict) or not isinstance(member_styles, list):
        raise HTTPException(
            status_code=422, detail="body needs {cluster: {cluster_id, theme, brief_ids}, member_styles: [...]}"
        )
    try:
        draft = draft_contract(cluster, [s for s in member_styles if isinstance(s, str)], created_by=actor.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    try:
        record = store.create(draft)
    except CollectionExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_errors(exc))
    writer.record(
        actor_user_id=actor.user_id,
        action="collection.candidate",
        entity_type="collection",
        entity_id=record["contract"]["collection_id"],
        before={"cluster_id": cluster.get("cluster_id")},
        after=record["contract"],
    )
    return {"cluster_id": cluster.get("cluster_id"), **_detail(record)}


@router.post("/{slug}/approve")
def approve_collection(
    slug: str,
    actor: Actor = DecideAllowed,
    store: CollectionsStore = Depends(get_collections_store),
    writer: AuditWriter = Depends(get_audit_writer),
    service: HitlService = Depends(get_hitl_service),
    gates=Depends(get_gate_source),
    index=Depends(get_approval_index),
    expected_mtime: Optional[float] = Query(default=None),
) -> dict[str, Any]:
    """Approve a candidate: atomic active-stamp + audit + best-effort resume (A8)."""
    try:
        before = store.get(slug)["contract"]
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    if before["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"only drafts can be approved (status: {before['status']})",
        )
    missing = _completeness_errors(before)
    if missing:
        raise HTTPException(status_code=422, detail=missing)
    try:
        record = store.transition(slug, to_status="active", stamp={"approved_at": _utcnow()}, expected_mtime=expected_mtime)
    except MtimeConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_errors(exc))
    writer.record(
        actor_user_id=actor.user_id,
        action="collection.approve",
        entity_type="collection",
        entity_id=slug,
        before=before,
        after=record["contract"],
    )
    resume = _resume_collection_gate(slug, actor_user_id=actor.user_id, service=service, gates=gates, index=index)
    return {**_detail(record), "resume": resume}


@router.post("/{slug}/retire")
def retire_collection(
    slug: str,
    payload: dict[str, Any],
    actor: Actor = AdminOnly,
    store: CollectionsStore = Depends(get_collections_store),
    writer: AuditWriter = Depends(get_audit_writer),
    expected_mtime: Optional[float] = Query(default=None),
) -> dict[str, Any]:
    """Retire a collection with an optional survivor product exception (A9)."""
    survivors = payload.get("survivor_product_ids") or []
    if not isinstance(survivors, list) or any(not isinstance(s, str) for s in survivors):
        raise HTTPException(status_code=422, detail="survivor_product_ids must be a list of strings")
    try:
        before = store.get(slug)["contract"]
    except CollectionNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown collection")
    if before["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"only active collections can retire (status: {before['status']})",
        )
    try:
        record = store.transition(
            slug,
            to_status="retired",
            stamp={"retired_at": _utcnow(), "survivor_products": survivors},
            expected_mtime=expected_mtime,
        )
    except MtimeConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_errors(exc))
    writer.record(
        actor_user_id=actor.user_id,
        action="collection.retire",
        entity_type="collection",
        entity_id=slug,
        before=before,
        after=record["contract"],
    )
    return {**_detail(record), "survivors_live": survivors}


def _resume_collection_gate(
    slug: str, *, actor_user_id: str, service: HitlService, gates, index
) -> dict[str, Any]:
    """A8: if this candidate backs a paused collection-gate run, resume it.

    Best-effort: the YAML activation above is authoritative. An ambiguous
    multi-cluster gate (or a consumed one) surfaces as not-resumed with a
    reason — the Approvals queue remains the disambiguation path.
    """
    paused: Optional[dict[str, Any]] = None
    try:
        live = gates.list_interrupts()
    except Exception:  # noqa: BLE001 - resume is best-effort, never fails approval
        return {"attempted": False, "resumed": False, "reason": "gate scan unavailable"}
    for info in live:
        if info.node != "contract_approval":
            continue
        contracts = (info.payload.get("contracts") or []) if isinstance(info.payload, dict) else []
        if any(isinstance(c, dict) and c.get("collection_id") == slug for c in contracts):
            paused = {"run_id": info.run_id, "node": info.node}
            break
    if paused is None:
        return {"attempted": False, "resumed": False, "paused_run": None}
    row = next(
        (r for r in index.list_open() if r["run_id"] == paused["run_id"] and r["node"] == paused["node"]),
        None,
    )
    if row is None:
        return {"attempted": False, "resumed": False, "paused_run": paused, "reason": "no open index row"}
    try:
        decision = service.decide(row["id"], action="approve", note=None, selection=None, actor_user_id=actor_user_id)
    except (HitlAmbiguous, HitlStale) as exc:
        return {"attempted": True, "resumed": False, "paused_run": paused, "reason": str(exc)}
    except Exception as exc:  # noqa: BLE001 - best-effort resume
        return {"attempted": True, "resumed": False, "paused_run": paused, "reason": f"{type(exc).__name__}: {exc}"}
    return {"attempted": True, "resumed": decision.get("resumed", False), "paused_run": paused}
