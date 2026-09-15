"""Aesthetic QC image reference contracts.

Regression: the render node records a LOCAL artifact path and aesthetic QC passed
that string to OpenRouter as `image_url.url`, which rejects it with HTTP 400 —
how the first live run died at the vision step.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from pipeline.nodes.aesthetic_qc import image_ref

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-ihdr-body"


def test_local_artifact_is_inlined_as_a_data_uri(tmp_path: Path) -> None:
    artifact = tmp_path / "render.png"
    artifact.write_bytes(PNG_BYTES)

    ref = image_ref(str(artifact))

    assert ref.startswith("data:image/png;base64,")
    assert base64.b64decode(ref.split(",", 1)[1]) == PNG_BYTES


def test_http_and_data_urls_pass_through_unchanged() -> None:
    for url in (
        "https://cdn.example/render.png",
        "http://internal/render.png",
        "data:image/png;base64,AAAA",
    ):
        assert image_ref(url) == url


def test_missing_artifact_is_loud_not_silent(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="render artifact not found"):
        image_ref(str(tmp_path / "absent.png"))
