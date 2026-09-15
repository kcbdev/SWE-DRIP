"""Tolerant JSON extraction for model output.

Models are asked to "reply ONLY with JSON" but frequently wrap it in a markdown
fence or add a sentence of prose. Strict `json.loads` then fails on otherwise
perfect output — which is how the first live aesthetic-QC call died ("vision
model returned unusable scores: Expecting value: line 1 column 1"). Parsing is
where an LLM boundary is actually crossed, so it belongs in one tested helper
rather than being re-implemented per node.

Extraction is conservative and never guesses values: it unwraps fences and
surrounding prose, then requires a real JSON object. Anything else is loud.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class ModelJSONError(ValueError):
    """Model output was not a JSON object, even after unwrapping."""


def parse_json_object(text: Any) -> dict[str, Any]:
    """Parse a JSON object out of model output.

    Order: raw, then inside a ```/```json fence, then the outermost braces.
    Raises :class:`ModelJSONError` (a ``ValueError``) with a short, safe excerpt
    of what was received.
    """
    if not isinstance(text, str) or not text.strip():
        raise ModelJSONError(f"expected JSON object text, got {type(text).__name__}")

    candidates: list[str] = [text.strip()]

    fenced = _FENCE.search(text)
    if fenced:
        candidates.append(fenced.group(1).strip())
        # A fence may itself contain prose + braces; the brace slice below covers it.

    stripped = candidates[-1]
    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ModelJSONError(f"model did not return a JSON object: {_excerpt(text)}")


def _excerpt(text: str, limit: int = 120) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else f"{flat[:limit]}…"
