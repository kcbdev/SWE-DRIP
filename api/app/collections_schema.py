"""Collection contract schema — pydantic mirror of data spec §1.1.

Locked vocabularies are imported from the pipeline contract node (single
source for the §1.1 enums); ``extra="forbid"`` everywhere so unknown fields
fail loudly (spec C6). ``style_archetype`` stays a non-empty string here
because drafts carry free member styles — the locked 7-style vocabulary
lives in ``collections/styles.yaml`` (see ``pipeline/styles.py``) and is
enforced at approval time (completeness gate), not at drafting.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pipeline.nodes.contract import DESIGN_TYPES, PLACEMENT_ZONES, SLEEVE_ZONES, STATUS_VALUES

Status = Literal["draft", "active", "retired"]
assert set(STATUS_VALUES) == {"draft", "active", "retired"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IllustrationRules(StrictModel):
    line_weight: Optional[str] = None
    palette: list[str] = Field(default_factory=list)
    no_mixed_styles: Literal[True]


class GarmentColorway(StrictModel):
    base: str
    contrast_pass: bool

    @field_validator("base")
    @classmethod
    def _non_empty_base(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("base must be non-empty")
        return value


class PlacementTemplate(StrictModel):
    design_type: Literal["hero-icon", "wordmark", "log-block", "brand-mark-only"]
    front: Literal["none", "chest", "full"]
    back: Literal["none", "chest", "full"]
    sleeve: Literal["none", "chest", "full", "small-mark"]


assert set(DESIGN_TYPES) == {"hero-icon", "wordmark", "log-block", "brand-mark-only"}
assert set(PLACEMENT_ZONES) == {"none", "chest", "full"}
assert set(SLEEVE_ZONES) == {"none", "chest", "full", "small-mark"}


class KpiThresholds(StrictModel):
    min_units: Optional[float] = Field(default=None, ge=0)
    min_conversion: Optional[float] = Field(default=None, ge=0)
    eval_window_days: Optional[float] = Field(default=None, ge=0)


class InspirationRef(StrictModel):
    url: str
    note: str = ""

    @field_validator("url")
    @classmethod
    def _non_empty_url(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("inspiration ref url must be non-empty")
        return value


def _relative_artifact_refs(values: list[str], field: str) -> list[str]:
    """Mood-board refs are collection-relative artifact paths (PBI-048).

    Absolute paths (POSIX and Windows), parent escapes, scheme URIs
    (including `data:`), and blanks are rejected loudly: boards are served
    same-origin from the collection's asset dir, never hotlinked.
    """
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{field} entries must be non-empty strings")
        text = value.strip()
        if not text:
            raise ValueError(f"{field} entries must be non-empty strings")
        lowered = text.lower()
        if (
            text.startswith("/")
            or text.startswith("\\")
            or "://" in lowered
            or ":" in text.split("/")[0]
            or any(part == ".." for part in text.replace("\\", "/").split("/"))
        ):
            raise ValueError(f"{field} must be relative artifact refs, got {value!r}")
    return values


class CollectionContract(StrictModel):
    collection_id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    theme: str
    status: Status
    style_archetype: str
    illustration_rules: IllustrationRules
    garment_colorways: list[GarmentColorway] = Field(default_factory=list)
    placement_templates: list[PlacementTemplate] = Field(default_factory=list)
    product_count_target: Optional[int] = Field(default=None, ge=1)
    lifecycle_days: Optional[int] = Field(default=None, ge=1)
    kpi_thresholds: KpiThresholds
    created_by: str
    created_at: str
    approved_at: Optional[str] = None
    retired_at: Optional[str] = None
    # A9 survivor exception (collections spec Decisions 2026-09-14): product ids
    # that stay live and flagged after retirement. Empty (default) when none —
    # the catalog mirror (PBI-030) reads this to honor the exception.
    survivor_products: list[str] = Field(default_factory=list)
    # V2 visual direction (collection-research spec C2): all optional so v1
    # contracts validate byte-identically. style_archetype itself stays a
    # non-empty string here — drafts carry free member styles; the locked
    # vocabulary is enforced at approval (completeness gate), never at
    # drafting.
    style_descriptors: list[str] = Field(default_factory=list)
    mood_board: list[str] = Field(default_factory=list)
    inspiration_refs: list[InspirationRef] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    board_version: int = Field(default=1, ge=1)

    @field_validator("theme", "style_archetype", "created_by", "created_at")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value

    @field_validator("mood_board")
    @classmethod
    def _board_refs_relative(cls, value: list[str]) -> list[str]:
        return _relative_artifact_refs(value, "mood_board")
