"""Aesthetic-QC rubric (spec C9 + collection-research C5).

Four core criteria, 70 pass threshold (all four must score ≥ 70), capped
regeneration. The regeneration cap is a CONSTANT here — changing it is a spec
change per the PBI-013 refinement rule, not a code tweak.

Cap choice (flagged for founder confirmation): ``MAX_REGEN_RETRIES = 2``
(initial render + up to 2 regenerations = 3 image calls max per design).
Cost-conservative: image calls are the most expensive step under the $130/mo
cap. Raise only via spec amendment.

Style conformance (PBI-051) is the fifth, board-scored criterion: it is
OPTIONAL in the payload because pre-board collections have no board to
score against. Absent → ``unscored`` (visible, never a guessed pass, and
the run keeps going honestly); present and below threshold → fail with the
criterion named.
"""

from __future__ import annotations

from typing import Any

from .prompts import build_qc_prompt  # noqa: F401 — canonical home is prompts.py

CRITERIA = ("style_cohesion", "focal_point", "placement_fit", "contrast")

# Fifth criterion, board-scored (PBI-051). Optional in payloads: pre-board
# verdicts predate it and must keep evaluating honestly.
STYLE_CRITERION = "style_conformance"

PASS_THRESHOLD = 70

MAX_REGEN_RETRIES = 2

# Stored with every aesthetic-QC verdict (design-qc spec Decisions) so
# calibration stays interpretable if the rubric prompt ever changes. Bump on
# any prompt change; scoring-logic changes need a spec amendment (PBI-022).
# v2: style_conformance criterion added (PBI-051).
RUBRIC_VERSION = 2


__all__ = [
    "CRITERIA",
    "PASS_THRESHOLD",
    "MAX_REGEN_RETRIES",
    "RUBRIC_VERSION",
    "build_qc_prompt",
    "parse_scores",
    "evaluate",
    "rejection_feedback",
]


def parse_scores(payload: Any) -> dict[str, int]:
    """Validate a vision score payload; loud on malformed scores.

    The four core criteria are required; ``style_conformance`` is optional
    (pre-board collections have no board to score against).
    """
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
    if STYLE_CRITERION in payload:
        value = payload[STYLE_CRITERION]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"QC criterion {STYLE_CRITERION!r} must be a number 0–100")
        if not 0 <= value <= 100:
            raise ValueError(f"QC criterion {STYLE_CRITERION!r}={value} out of range 0–100")
        scores[STYLE_CRITERION] = int(value)
    return scores


def style_status(scores: dict[str, int]) -> str:
    """Style-conformance standing: pass, fail, or unscored (no board)."""
    if STYLE_CRITERION not in scores:
        return "unscored"
    return "pass" if scores[STYLE_CRITERION] >= PASS_THRESHOLD else "fail"


def evaluate(scores: dict[str, int]) -> dict[str, Any]:
    """All four core criteria ≥ 70 passes; anything below fails.

    A scored-but-failing style_conformance fails the verdict with the
    criterion named (it joins ``failing``, so regen feedback carries it).
    An unscored style never flips a verdict — it is carried visibly instead.
    """
    failing = [c for c in CRITERIA if scores[c] < PASS_THRESHOLD]
    style = style_status(scores)
    if style == "fail":
        failing = [*failing, STYLE_CRITERION]
    return {
        "scores": dict(scores),
        "pass_threshold": PASS_THRESHOLD,
        "result": "pass" if not failing else "fail",
        "failing": failing,
        "style_status": style,
    }


def rejection_feedback(evaluation: dict[str, Any], attempt: int) -> str:
    """Feedback text fed into the next render prompt (asserted in tests)."""
    parts = [
        f"{criterion} scored {evaluation['scores'][criterion]}/100 "
        f"(threshold {PASS_THRESHOLD})"
        for criterion in evaluation["failing"]
    ]
    return f"Regeneration required (attempt {attempt} failed): " + "; ".join(parts)
