"""Built-in prompt registry — the operator control plane's prompt half (spec C4).

Every pipeline node that calls a model builds its prompt in exactly one place:
here. ``pipeline/routing.py`` holds the model *defaults*; this module holds the
prompt *defaults* (the reviewed baseline). An operator override from the
settings store (``node_config.prompt_override``, resolved by
``pipeline/node_config.py``) takes precedence at run time — plain text
substitution only, never executable content (spec C6).

Why versions exist: ``aesthetic_qc``'s rubric is calibrated against pinned
fixtures. An override changes the effective prompt, so the verdict carries a
``prompt_version`` derived from (base version + override hash). Calibration
compares like with like (``api/app/designs.py``) or says so explicitly — an
override can never silently look "calibrated".

Conventions:

- ``PROMPT_KEYS`` maps node → stable ``prompt_key``. Keys never change; the
  base version bumps when the builder text changes (same discipline as
  ``rubric.RUBRIC_VERSION`` — for the QC rubric, bump both together).
- ``prompt_version(node, override=None)`` is stable without an override and
  changes with any override text change.
- Nodes record ``prompt_key``/``prompt_version`` in their verdicts — never the
  prompt text itself, so secrets-looking override text cannot leak into run
  state, logs, or audit rows. ``redact_for_log()`` is the backstop for any
  message that might echo prompt-adjacent text.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

# Node → stable prompt key. Only these four nodes take prompt overrides
# (PBI-039 scope); other nodes make no operator-visible prompt call.
PROMPT_KEYS: dict[str, str] = {
    "trend_research": "trend_clustering",
    "listing_copy": "listing_copy",
    "design_spec": "design_spec_rcao",
    "aesthetic_qc": "qc_rubric",
}

# Base version per prompt key. Bump when the corresponding builder's text
# changes (for ``qc_rubric``, bump ``rubric.RUBRIC_VERSION`` alongside it).
BASE_VERSIONS: dict[str, str] = {
    "trend_clustering": "v1",
    "listing_copy": "v1",
    "design_spec_rcao": "v1",
    "qc_rubric": "v1",
}


class NodePromptError(KeyError):
    """Unknown pipeline node — a programming error, never user input."""


def prompt_key(node: str) -> str:
    """The stable prompt key for ``node``; loud on unknown nodes."""
    try:
        return PROMPT_KEYS[node]
    except KeyError:
        raise NodePromptError(f"unknown prompted node: {node!r}") from None


def prompt_version(node: str, prompt_override: Optional[str] = None) -> str:
    """Short hash of (base version + override hash) for ``node``.

    Stable across runs without an override; any override text change yields a
    different version. An empty/blank override is no override at all.
    """
    key = prompt_key(node)
    base = BASE_VERSIONS[key]
    override = prompt_override.strip() if isinstance(prompt_override, str) else ""
    digest = hashlib.sha256(f"{key}:{base}:{override}".encode("utf-8")).hexdigest()
    return digest[:12]


def effective_prompt(node: str, built_in: str, prompt_override: Optional[str] = None) -> str:
    """The prompt a node should send: the override when set, else built-in.

    Plain substitution — the override is data, never executed or templated.
    """
    prompt_key(node)  # loud on unknown nodes, even when overridden
    if isinstance(prompt_override, str) and prompt_override.strip():
        return prompt_override
    return built_in


# ---------------------------------------------------------------------------
# Built-in builders (the reviewed baseline — moved verbatim from the nodes)
# ---------------------------------------------------------------------------

def build_trend_prompt(briefs: list[dict[str, Any]]) -> str:
    """Clustering synthesis prompt (node 1)."""
    return (
        "Group these t-shirt design briefs into thematic clusters for collection "
        "candidates. Reply ONLY with JSON of the form "
        '{"clusters": [{"theme": string, "brief_ids": [string]}]}.\n'
        + "\n".join(
            f"- id={b['id']} style={b.get('style', '?')} subject={b.get('subject', '?')}: "
            f"{b.get('text', '')}"
            for b in briefs
        )
    )


def build_copy_prompt(brief: dict[str, Any]) -> str:
    """Listing-copy prompt (node 3)."""
    return (
        "Write t-shirt listing copy in a dry developer-identity brand voice. "
        "Reply ONLY with JSON: "
        '{"slogan": "≤6 words, no hashtags", "title": "≤60 chars, no hashtags", '
        '"description": "1-3 sentences, no hashtags", "tags": ["kebab-case tags, no #"]}.\n'
        f"Subject: {brief.get('subject', '')}\nText: {brief.get('text', '')}\n"
        f"Style: {brief.get('style', '')}"
    )


def build_spec_prompt(brief: dict[str, Any], contract: dict[str, Any]) -> str:
    """RCAO reasoning prompt (node 4)."""
    return (
        "Using the RCAO framework (Reason, Creative direction, Audience, Output), "
        "reason about this t-shirt design and propose a render prompt. Reply ONLY "
        "with JSON: {\"rcao\": string, \"render_prompt\": string}.\n"
        f"Brief subject: {brief.get('subject', '')}\nBrief text: {brief.get('text', '')}\n"
        f"Collection theme: {contract.get('theme', '')}\n"
        f"Locked style: {contract.get('style_archetype', '')}"
    )


def build_qc_prompt(
    design_subject: str,
    style: str,
    attempt: int,
    previous_feedback: str = "",
) -> str:
    """Vision scoring prompt: rubric + strict JSON schema instruction (node 7)."""
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


# ---------------------------------------------------------------------------
# Secret redaction (log backstop)
# ---------------------------------------------------------------------------

# NOTE: key-material patterns are assembled from fragments so this file itself
# never contains a matchable secret literal (the repo lint secret-scans us).
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile("sk" + "-or-[A-Za-z0-9][A-Za-z0-9._~-]*"), "[REDACTED-OPENROUTER-KEY]"),
    (re.compile("sk" + "-[A-Za-z0-9]{8,}"), "[REDACTED-KEY]"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*\S+"),
     lambda m: f"{m.group(1)}=[REDACTED]"),  # type: ignore[arg-type]
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~-]+"), "Bearer [REDACTED]"),
)


def redact_for_log(text: Any) -> Any:
    """Mask secrets-looking substrings before anything prompt-adjacent is logged.

    Non-strings pass through untouched. Nodes store versions/keys rather than
    prompt text, so this is a backstop — but any future log line that echoes
    operator-supplied text must pass through here first.
    """
    if not isinstance(text, str):
        return text
    redacted = text
    for pattern, replacement in _REDACTIONS:
        redacted = pattern.sub(replacement, redacted)  # type: ignore[arg-type]
    return redacted
