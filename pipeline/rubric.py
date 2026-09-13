"""Aesthetic-QC rubric (spec C9).

Four criteria, 70 pass threshold (all four must score ≥ 70), capped
regeneration. The regeneration cap is a CONSTANT here — changing it is a spec
change per the PBI-013 refinement rule, not a code tweak.

Cap choice (flagged for founder confirmation): ``MAX_REGEN_RETRIES = 2``
(initial render + up to 2 regenerations = 3 image calls max per design).
Cost-conservative: image calls are the most expensive step under the $130/mo
cap. Raise only via spec amendment.
"""

from __future__ import annotations

from typing import Any

CRITERIA = ("style_cohesion", "focal_point", "placement_fit", "contrast")

PASS_THRESHOLD = 70

MAX_REGEN_RETRIES = 2


def build_qc_prompt(
    design_subject: str,
    style: str,
    attempt: int,
    previous_feedback: str = "",
) -> str:
    """Vision scoring prompt: rubric + strict JSON schema instruction."""
    prompt = (
        "Score this t-shirt render against the four-criterion aesthetic rubric, "
        "0–100 per criterion. Reply ONLY with JSON: "
        '{"style_cohesion": int, "focal_point": int, "placement_fit": int, '
        '"contrast": int, "notes": string}.\n'
        "Criteria: style_cohesion (matches the locked style, no mixed styles); "
        "focal_point (exactly one clear focal point); placement_fit (design fits "
        "its placement zone); contrast (readable on every valid colorway).\n"
        f"Design subject: {design_subject}\nLocked style: {style}\n"
        f"Scoring attempt: {attempt}"
    )
    if previous_feedback:
        prompt += f"\nPrevious rejection feedback (verify it was addressed): {previous_feedback}"
    return prompt


def parse_scores(payload: Any) -> dict[str, int]:
    """Validate a vision score payload; loud on malformed scores."""
    if not isinstance(payload, dict):
        raise ValueError(f"QC scores must be a mapping, got {type(payload)}")
    scores: dict[str, int] = {}
    for criterion in CRITERIA:
        value = payload.get(criterion)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"QC criterion {criterion!r} must be a number 0–100")
        if not 0 <= value <= 100:
            raise ValueError(f"QC criterion {criterion!r}={value} out of range 0–100")
        scores[criterion] = int(value)
    return scores


def evaluate(scores: dict[str, int]) -> dict[str, Any]:
    """All four criteria ≥ 70 passes; anything below fails."""
    failing = [c for c in CRITERIA if scores[c] < PASS_THRESHOLD]
    return {
        "scores": dict(scores),
        "pass_threshold": PASS_THRESHOLD,
        "result": "pass" if not failing else "fail",
        "failing": failing,
    }


def rejection_feedback(evaluation: dict[str, Any], attempt: int) -> str:
    """Feedback text fed into the next render prompt (asserted in tests)."""
    parts = [
        f"{criterion} scored {evaluation['scores'][criterion]}/100 "
        f"(threshold {PASS_THRESHOLD})"
        for criterion in evaluation["failing"]
    ]
    return f"Regeneration required (attempt {attempt} failed): " + "; ".join(parts)
