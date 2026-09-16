"""Board-image resolution for QC (PBI-051) — offline, tmp collections root."""

from __future__ import annotations

import base64
import struct
from pathlib import Path

import pytest

from api.app.runs import resolve_board_image


def _png_bytes() -> bytes:
    ihdr = struct.pack(">IIBBBBB", 16, 16, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4


@pytest.fixture()
def rooted(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("SWE_DRIP_COLLECTIONS_DIR", str(tmp_path / "collections"))
    return tmp_path / "collections"


class TestResolveBoardImage:
    def test_first_existing_ref_inlined(self, rooted: Path) -> None:
        assets = rooted / "vibe.assets"
        assets.mkdir(parents=True)
        (assets / "board.png").write_bytes(_png_bytes())
        uri = resolve_board_image({"collection_id": "vibe",
                                   "mood_board": ["missing.png", "board.png"]})
        assert uri is not None and uri.startswith("data:image/png;base64,")
        assert base64.b64decode(uri.split(",", 1)[1]) == _png_bytes()

    def test_missing_everything_is_none(self, rooted: Path) -> None:
        assert resolve_board_image({"collection_id": "vibe", "mood_board": []}) is None
        assert resolve_board_image({}) is None
        assert resolve_board_image({"collection_id": "vibe",
                                    "mood_board": ["../escape.png"]}) is None

    def test_non_image_skipped(self, rooted: Path) -> None:
        assets = rooted / "vibe.assets"
        assets.mkdir(parents=True)
        (assets / "note.txt").write_bytes(b"hello")
        assert resolve_board_image({"collection_id": "vibe",
                                    "mood_board": ["note.txt"]}) is None

    def test_never_raises(self, rooted: Path) -> None:
        assert resolve_board_image(None) is None  # type: ignore[arg-type]
        assert resolve_board_image({"collection_id": "vibe",
                                    "mood_board": "not-a-list"}) is None
