"""Fact Log contracts: Fact, FactBatch, FactSegmentManifest."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.model_layer.canon import content_hash, to_canonical_bytes
from polisyos.ir.kernel.base import ARTIFACT_ID_PATTERN, ID_PATTERN, KernelModel, reject_float

if TYPE_CHECKING:
    from decimal import Decimal
else:
    from decimal import Decimal


class FactProvenance(KernelModel):
    """Fact provenance public type."""

    source_id: str = Field(..., pattern=ID_PATTERN)
    license: str
    raw_hash: str
    ingestion_run_id: str | None = None
    script_hash: str | None = None
    notes: list[str] = Field(default_factory=list)


class FactTrust(KernelModel):
    """Fact trust public type."""

    confidence: float | None = Field(None, ge=0.0, le=1.0)
    method: str | None = None
    policy_id: str | None = Field(None, pattern=ID_PATTERN)
    notes: list[str] = Field(default_factory=list)


class FactPIIEntity(KernelModel):
    """Fact PII entity public type."""

    entity_type: str
    severity: str
    score: float | None = Field(None, ge=0.0, le=1.0)
    column: str | None = None
    start: int | None = Field(None, ge=0)
    end: int | None = Field(None, ge=0)
    redacted_text: str = "***"


class FactLegal(KernelModel):
    """Fact legal public type."""

    pii_class: str | None = None
    access_tier: str | None = None
    basis: str | None = None
    notes: list[str] = Field(default_factory=list)
    pii_detected: list[FactPIIEntity] = Field(default_factory=list)
    pii_scan_timestamp: str | None = None
    pii_max_severity: str | None = None


def canonical_tx_time(value: datetime | str) -> str:
    """Normalize a transaction timestamp to aware UTC ``Z`` form.

    ``Fact.tx_time`` is part of the fact-log ordering contract and must be
    caller-supplied. Naive datetimes/strings are rejected instead of being
    guessed from host locale.
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("tx_time must be an ISO-8601 datetime") from exc
    else:
        raise ValueError("tx_time must be datetime or ISO-8601 string")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("tx_time must include timezone information")
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def utc_tx_time() -> str:
    """Return the current UTC transaction timestamp for explicit factories."""
    return canonical_tx_time(datetime.now(UTC))


class Fact(KernelModel):
    """Fact public type."""

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    fact_id: str = Field(..., pattern=ARTIFACT_ID_PATTERN)
    subject_id: str = Field(..., pattern=ID_PATTERN)
    predicate_id: str = Field(..., pattern=ID_PATTERN)
    object_value: str | int | bool | Decimal | None = Field(None, serialization_alias="object")
    target_id: str | None = Field(None, pattern=ID_PATTERN)
    valid_time: str | int | None = None
    tx_time: str
    provenance: FactProvenance
    trust: FactTrust | None = None
    legal: FactLegal | None = None

    @field_validator("tx_time", mode="before")
    @classmethod
    def normalize_tx_time(cls, value: datetime | str) -> str:
        return canonical_tx_time(value)

    @model_validator(mode="after")
    def ensure_object(self) -> Fact:
        if self.object_value is None and self.target_id is None:
            raise ValueError("Fact requires object_value or target_id")
        return self


def build_fact_id(payload: Any) -> str:
    """Compute deterministic fact_id as sha256 of canonical payload bytes."""
    canon = to_canonical_bytes(payload)
    digest = content_hash(canon)
    return f"sha256:{digest}"


class FactBatch(BaseModel):
    """Fact batch public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    facts: list[Fact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_floats(cls, value: Any) -> Any:
        reject_float(value)
        return value


class FactSegmentManifest(KernelModel):
    """Fact segment manifest data model."""

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    segment_id: str = Field(..., pattern=ID_PATTERN)
    path: str
    row_count: int
    sha256: str
    time_start: str | int | None = None
    time_end: str | int | None = None
    null_count: int | None = None
    duplicate_count: int | None = None
    stats: dict[str, int | float | str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
