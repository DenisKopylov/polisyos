"""Public fabric manifest module API."""

from pydantic import BaseModel, ConfigDict, Field

from polisyos.fabric.temporal import utc_now


class CoverageMetrics(BaseModel):
    """Coverage metrics data model."""

    time_start: str | None = Field(
        default=None,
        description="UTC-aware ISO-8601 start timestamp when present.",
    )
    time_end: str | None = Field(
        default=None,
        description="UTC-aware ISO-8601 end timestamp when present.",
    )
    region_coverage: str | None = None

    model_config = ConfigDict(extra="forbid")


class QualityMetrics(BaseModel):
    """Quality metrics data model."""

    missing_rate: float = Field(..., ge=0.0, le=1.0)
    duplicate_rate: float = Field(..., ge=0.0, le=1.0)
    outlier_rate: float = Field(..., ge=0.0, le=1.0)
    coverage: CoverageMetrics

    model_config = ConfigDict(extra="forbid")


class ReconciliationReport(BaseModel):
    """Reconciliation report data model."""

    status: str
    tolerance: float
    total_outflow: float
    total_inflow: float
    diff: float
    per_type: dict[str, dict[str, float]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class DatasetManifest(BaseModel):
    """Dataset manifest data model.

    Fabric timestamp fields are UTC-aware ISO-8601 strings.
    """

    dataset_name: str
    source: str
    license: str
    raw_hash: str
    schema_version: str
    row_count: int
    pii_flags: dict[str, bool]
    quality: QualityMetrics
    reconciliation: ReconciliationReport | None = None
    created_at: str = Field(
        default_factory=lambda: utc_now().isoformat(),
        description="UTC-aware ISO-8601 creation timestamp.",
    )

    model_config = ConfigDict(extra="forbid")
