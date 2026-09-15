"""Tolerant model-JSON parsing contracts.

The first live aesthetic-QC call died because the vision model fenced its JSON
and the node used strict `json.loads`. This is the boundary where LLM output
meets the pipeline, so it is one tested helper.
"""

from __future__ import annotations

import pytest

from pipeline.json_parse import ModelJSONError, parse_json_object


def test_plain_json_object_parses() -> None:
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_markdown_fence_is_unwrapped() -> None:
    assert parse_json_object('```json\n{"style_cohesion": 80}\n```') == {"style_cohesion": 80}
    assert parse_json_object('```\n{"a": 2}\n```') == {"a": 2}


def test_prose_around_the_object_is_ignored() -> None:
    text = 'Here is my assessment:\n{"focal_point": 90}\nHope that helps!'
    assert parse_json_object(text) == {"focal_point": 90}


def test_fenced_json_with_leading_prose() -> None:
    text = 'Sure!\n```json\n{"contrast": 70}\n```\nDone.'
    assert parse_json_object(text) == {"contrast": 70}


def test_nested_braces_use_the_outermost_object() -> None:
    assert parse_json_object('{"a": {"b": 1}}') == {"a": {"b": 1}}


@pytest.mark.parametrize("bad", ["", "   ", "no json here", "[1, 2, 3]", "42"])
def test_non_object_output_is_loud(bad: str) -> None:
    with pytest.raises(ModelJSONError):
        parse_json_object(bad)


def test_non_string_output_is_loud() -> None:
    with pytest.raises(ModelJSONError, match="list"):
        parse_json_object(["not", "text"])


def test_error_excerpt_is_short_and_flat() -> None:
    with pytest.raises(ModelJSONError) as excinfo:
        parse_json_object("x" * 500)
    message = str(excinfo.value)
    assert len(message) < 220
    assert "\n" not in message
