"""Design detail + calibration derivation (spec C2/C4).

Pure mappers over checkpointer run state + ``hitl_approvals`` decision rows —
no new store (spec Decisions: the checkpointer remains the score source).
Missing state surfaces as explicit nulls, never synthesized values
(refinement rule: schema gaps go to the pipeline spec, not the router).
"""

from __future__ import annotations

from typing import Any, Optional


def design_detail_from_state(values: dict[str, Any], run_id: str) -> dict[str, Any]:
    """Map one run's state values to the design-detail shape (pure)."""
    render = values.get("render_result") or values.get("render") or {}
    qc = values.get("aesthetic_qc") or {}
    scores = qc.get("scores")
    contract = values.get("collection_contract") or {}
    return {
        "design_id": values.get("design_id"),
        "run_id": run_id,
        "render": {
            "file_url": render.get("file_url"),
            "model_used": render.get("model_used"),
            "colorways_valid": render.get("colorways_valid") or [],
        },
        "qc": {
            "scores": scores,
            "pass_threshold": qc.get("pass_threshold", 70),
            "result": qc.get("result"),
            "failing": qc.get("failing") or [],
            "rubric_version": qc.get("rubric_version"),
            "prompt_key": qc.get("prompt_key"),
            "prompt_version": qc.get("prompt_version"),
            "attempts": qc.get("attempts"),
            "model_used": qc.get("model_used"),
        }
        if qc
        else None,
        "placement": values.get("placement"),
        "colorways": values.get("colorways") or render.get("colorways_valid") or [],
        "context": {
            "brief": values.get("brief"),
            "collection_id": values.get("collection_id") or contract.get("collection_id"),
            "collection_contract": contract or None,
        },
    }


def _agreement(qc_result: Optional[str], decisions: list[dict[str, Any]]) -> Optional[bool]:
    """Human-vs-rubric agreement. None when no human decision exists yet."""
    if not decisions:
        return None
    decided = [d for d in decisions if d.get("status") != "pending"]
    if not decided:
        return None
    if qc_result not in ("pass", "fail", "fail-human-review"):
        return None
    rubric_says_approve = qc_result == "pass"
    human_approved = any(d.get("status") == "approved" for d in decided)
    human_rejected = any(d.get("status") in ("rejected", "regenerate_requested") for d in decided)
    if human_approved and not human_rejected:
        return rubric_says_approve is True
    if human_rejected and not human_approved:
        return rubric_says_approve is False
    return None  # mixed decisions — no single agreement statement


def _prompt_mismatch_note(qc: dict[str, Any]) -> Optional[str]:
    """Like-with-like guard (spec C4): an override changes the effective prompt,
    so a verdict recorded under a different prompt version must never silently
    look "calibrated". Returns a note when mismatched, else None.

    Verdicts that predate versioning carry no ``prompt_version`` — they were all
    recorded under the built-in prompt, so a missing version is treated as the
    current base version rather than a mismatch.
    """
    try:
        from pipeline.prompts import prompt_version as current_prompt_version
    except Exception:
        return None
    recorded = qc.get("prompt_version") or current_prompt_version("aesthetic_qc")
    current = current_prompt_version("aesthetic_qc")
    if recorded != current:
        return (
            f"prompt changed since this verdict (recorded {recorded} vs current "
            f"{current}) — agreement is unknown, not agreement"
        )
    return None


def calibration_for(
    detail: dict[str, Any], decisions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Side-by-side rubric verdict + human decision(s) for one design (pure)."""
    qc = detail.get("qc") or {}
    prompt_note = _prompt_mismatch_note(qc)
    agreement = None if prompt_note else _agreement(qc.get("result"), decisions)
    if prompt_note is not None:
        note: Optional[str] = prompt_note
    else:
        note = (
            None
            if decisions and agreement is not None
            else "no human decision recorded yet — agreement is unknown, not agreement"
        )
    return {
        "design_id": detail.get("design_id"),
        "run_id": detail.get("run_id"),
        "rubric": {
            "result": qc.get("result"),
            "scores": qc.get("scores"),
            "rubric_version": qc.get("rubric_version"),
            "prompt_version": qc.get("prompt_version"),
        },
        "human_decisions": [
            {
                "id": d.get("id"),
                "node": d.get("node"),
                "status": d.get("status"),
                "reviewer_user_id": d.get("reviewer_user_id"),
                "note": d.get("note"),
                "decided_at": d.get("decided_at"),
            }
            for d in decisions
        ],
        "agreement": agreement,
        "note": note,
    }
