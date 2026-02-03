from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, ConfigDict

from polisyos.ir.connectors import QualityTier, TrustLevel
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.kernel.numbers import DecimalValue


class ValidTimeRange(KernelModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    from_: str | None = Field(None, alias="from")
    to: str | None = Field(None, alias="to")


class QueryScope(KernelModel):
    jurisdiction: str | None = None
    valid_time: ValidTimeRange | None = None
    as_of: str | None = None


class Pagination(KernelModel):
    limit: int = Field(100, ge=1, le=10000)
    cursor: str | None = None


class QualityThresholds(KernelModel):
    min_quality_tier: QualityTier | None = None
    min_trust_level: TrustLevel | None = None
    min_confidence: DecimalValue | None = None


QueryValue = Annotated[str | int | bool | DecimalValue, Field()]


class DataFilter(KernelModel):
    column: str
    op: Literal["==", "!=", ">", "<", ">=", "<=", "in", "not_in"]
    value: QueryValue


class DataViewRequest(KernelModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    request_id: str
    scope: QueryScope = Field(default_factory=QueryScope)
    view_type: str
    metrics: list[str]
    filters: list[DataFilter] = Field(default_factory=list)
    aggregation: str | None = None
    pagination: Pagination = Field(default_factory=Pagination)
    access_tier: str | None = None


class DocQuery(KernelModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    scope: QueryScope = Field(default_factory=QueryScope)
    source_types: list[str] | None = None
    publisher: str | None = None
    doc_type: str | None = None
    language: str | None = None
    text_contains: str | None = None
    quality: QualityThresholds = Field(default_factory=QualityThresholds)
    pagination: Pagination = Field(default_factory=Pagination)


class ClaimQuery(KernelModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    scope: QueryScope = Field(default_factory=QueryScope)
    predicate_id: str | None = None
    subject_id: str | None = None
    domain: str | None = None
    quality: QualityThresholds = Field(default_factory=QualityThresholds)
    pagination: Pagination = Field(default_factory=Pagination)


class NormQuery(KernelModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    jurisdiction: str | None = None
    effective_at: str | None = None
    norm_pack_ids: list[str] | None = None
    pagination: Pagination = Field(default_factory=Pagination)


__all__ = [
    "QueryScope",
    "ValidTimeRange",
    "Pagination",
    "QualityThresholds",
    "DataFilter",
    "DataViewRequest",
    "DocQuery",
    "ClaimQuery",
    "NormQuery",
]
