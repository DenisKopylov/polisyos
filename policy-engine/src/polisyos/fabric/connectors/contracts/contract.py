"""
Connector-level schema contracts.

ConnectorSchemaContract binds a connector + dataset pattern to a concrete
DataSchema and quality guarantees, enabling fetch-time enforcement and
schema-aware cache invalidation.
"""
from __future__ import annotations

import fnmatch
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.canon import content_hash as compute_content_hash
from polisyos.fabric.finite import ensure_non_negative_finite, ensure_probability
from polisyos.ir.canon import CanonSpec, to_canonical_bytes

from .governance import SchemaApprovalMetadata
from .schema import DataSchema, SchemaVersion


CONTRACT_ID_PATTERN = (
    r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*"
    r"(?:\.[a-z][a-z0-9]*(?:_[a-z0-9]+)*)*$"
)


class FieldMapping(BaseModel):
    """Mapping from source payload path to internal schema field."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_path: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="JSON-path or dotted path in source payload",
    )
    target_field: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Target DataSchema field name",
    )
    transform: str | None = Field(
        default=None,
        max_length=128,
        description="Optional transform identifier (e.g. int, float, iso3166_alpha3)",
    )


class ConnectorSchemaContract(BaseModel):
    """
    Immutable contract between connector dataset output and internal schema.

    dataset_id supports shell-style wildcards, e.g. "NY.*" or "*".
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    contract_id: str = Field(
        ...,
        pattern=CONTRACT_ID_PATTERN,
        description="Globally unique contract ID",
    )
    connector_id: str = Field(..., min_length=1, max_length=256)
    dataset_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Dataset ID or wildcard pattern matched against FetchRequest.dataset_id",
    )

    connector_schema: DataSchema = Field(alias="schema")
    field_mappings: tuple[FieldMapping, ...] = Field(default=())

    min_completeness: float | None = Field(default=None, ge=0.0, le=1.0)
    field_completeness: dict[str, float] = Field(
        default_factory=dict,
        description="Per-column completeness thresholds in [0, 1]",
    )
    completeness_scope: Literal["full_dataset", "latest_window"] = "full_dataset"
    completeness_window_rows: int | None = Field(default=None, ge=1)

    max_staleness_hours: float | None = Field(default=None, ge=0.0)
    expected_row_count_range: tuple[int | None, int | None] = Field(default=(None, None))

    description: str = Field(default="", max_length=2048)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="", max_length=256)
    approval: SchemaApprovalMetadata = Field(default_factory=SchemaApprovalMetadata)

    @field_validator("min_completeness", mode="before")
    @classmethod
    def _validate_min_completeness(cls, value: object) -> float | None:
        if value is None:
            return None
        return ensure_probability(value, what="min_completeness")

    @field_validator("field_completeness", mode="before")
    @classmethod
    def _validate_field_completeness(
        cls, value: object
    ) -> dict[str, float]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise TypeError("field_completeness must be a mapping")
        return {
            field_name: ensure_probability(
                threshold,
                what=f"field_completeness[{field_name}]",
            )
            for field_name, threshold in value.items()
        }

    @field_validator("max_staleness_hours", mode="before")
    @classmethod
    def _validate_max_staleness_hours(cls, value: object) -> float | None:
        if value is None:
            return None
        return ensure_non_negative_finite(value, what="max_staleness_hours")

    @field_validator("expected_row_count_range", mode="before")
    @classmethod
    def _coerce_expected_row_count_range(
        cls, value: object
    ) -> tuple[int | None, int | None]:
        if value is None:
            return (None, None)
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError("expected_row_count_range must contain exactly two values")
        min_rows, max_rows = value
        return (None if min_rows is None else int(min_rows), None if max_rows is None else int(max_rows))

    @model_validator(mode="after")
    def _validate_consistency(self) -> "ConnectorSchemaContract":
        min_rows, max_rows = self.expected_row_count_range
        if min_rows is not None and min_rows < 0:
            raise ValueError("expected_row_count_range min must be >= 0")
        if max_rows is not None and max_rows < 0:
            raise ValueError("expected_row_count_range max must be >= 0")
        if min_rows is not None and max_rows is not None and min_rows > max_rows:
            raise ValueError("expected_row_count_range min must be <= max")

        if self.completeness_window_rows is not None and self.completeness_scope != "latest_window":
            raise ValueError(
                "completeness_window_rows is only allowed when completeness_scope=latest_window"
            )

        schema_fields = set(self.connector_schema.field_names())
        for field_name, threshold in self.field_completeness.items():
            if field_name not in schema_fields:
                raise ValueError(
                    f"field_completeness references unknown schema field '{field_name}'"
                )

        return self

    @property
    def schema(self) -> DataSchema:
        """Backwards-compatible accessor for callers using ``contract.schema``."""
        return self.connector_schema

    @property
    def schema_version(self) -> SchemaVersion:
        return self.connector_schema.version

    @property
    def content_hash(self) -> str:
        """
        Semantic hash for cache invalidation and artifact identity.

        Volatile metadata (created_at, created_by, description) is intentionally
        excluded so the hash changes only for behavioral contract changes.
        """
        payload = {
            "contract_id": self.contract_id,
            "connector_id": self.connector_id,
            "dataset_id": self.dataset_id,
            "schema_content_hash": self.connector_schema.content_hash,
            "field_mappings": [
                mapping.model_dump(mode="python") for mapping in self.field_mappings
            ],
            "min_completeness": self.min_completeness,
            "field_completeness": {
                key: self.field_completeness[key] for key in sorted(self.field_completeness)
            },
            "completeness_scope": self.completeness_scope,
            "completeness_window_rows": self.completeness_window_rows,
            "max_staleness_hours": self.max_staleness_hours,
            "expected_row_count_range": list(self.expected_row_count_range),
        }
        digest = compute_content_hash(
            to_canonical_bytes(payload, spec=CanonSpec(forbid_floats=False))
        )
        return f"sha256:{digest}"

    def matches_dataset(self, dataset_id: str) -> bool:
        """Return True when this contract applies to dataset_id."""
        return fnmatch.fnmatch(dataset_id, self.dataset_id)
