"""Collection contract schema — pydantic mirror of data spec §1.1.

Locked vocabularies are imported from the pipeline contract node (single
source for the §1.1 enums); ``extra="forbid"`` everywhere so unknown fields
fail loudly (spec C6). ``style_archetype`` stays a non-empty string: the "7
locked brand styles" are named nowhere in the spec kit (gap flagged in
PBI-011) — inventing the list would be fabrication.
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

    @field_validator("theme", "style_archetype", "created_by", "created_at")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be non-empty")
        return value
