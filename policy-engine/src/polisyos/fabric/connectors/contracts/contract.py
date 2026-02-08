"""
Connector-level schema contracts.

ConnectorSchemaContract binds a connector + dataset pattern to a concrete
DataSchema and quality guarantees, enabling fetch-time enforcement and
schema-aware cache invalidation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.canon import CanonSpec, to_canonical_bytes

from .schema import DataSchema, SchemaVersion


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

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_.]+$",
        description="Globally unique contract ID",
    )
    connector_id: str = Field(..., min_length=1, max_length=256)
    dataset_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Dataset ID or wildcard pattern matched against FetchRequest.dataset_id",
    )

    schema: DataSchema
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

        schema_fields = set(self.schema.field_names())
        for field_name, threshold in self.field_completeness.items():
            if not 0.0 <= threshold <= 1.0:
                raise ValueError(f"field_completeness[{field_name}] must be in [0, 1]")
            if field_name not in schema_fields:
                raise ValueError(
                    f"field_completeness references unknown schema field '{field_name}'"
                )

        return self

    @property
    def schema_version(self) -> SchemaVersion:
        return self.schema.version

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
            "schema_content_hash": self.schema.content_hash,
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
        digest = hashlib.sha256(
            to_canonical_bytes(payload, spec=CanonSpec(forbid_floats=False))
        ).hexdigest()
        return f"sha256:{digest}"

    def matches_dataset(self, dataset_id: str) -> bool:
        """Return True when this contract applies to dataset_id."""
        return fnmatch.fnmatch(dataset_id, self.dataset_id)
