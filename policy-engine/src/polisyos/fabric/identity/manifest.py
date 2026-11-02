"""Public fabric manifest module API."""

from pydantic import BaseModel, ConfigDict, Field

from polisyos.fabric.data_plane.temporal import utc_now


class CoverageMetrics(BaseModel):
    """Record the dataset's declared temporal and geographic coverage.

    The model carries optional start and end timestamp strings and an optional
    region-coverage description. Timestamp field descriptions specify
    UTC-aware ISO-8601 values; this DTO records those declarations rather than
    computing coverage from dataset rows.
    """

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
    """Record missing, duplicate, and outlier rates with coverage metadata.

    Each rate is constrained to the inclusive range from zero to one, and
    ``coverage`` carries the associated :class:`CoverageMetrics`. The model
    stores supplied metrics; it does not derive them from a dataset.
    """

    missing_rate: float = Field(..., ge=0.0, le=1.0)
    duplicate_rate: float = Field(..., ge=0.0, le=1.0)
    outlier_rate: float = Field(..., ge=0.0, le=1.0)
    coverage: CoverageMetrics

    model_config = ConfigDict(extra="forbid")


class ReconciliationReport(BaseModel):
    """Carry reported inflow/outflow totals and their reconciliation details.

    The report records a status, tolerance, aggregate totals, their reported
    difference, and optional per-type totals. It is a result-shaped DTO: it
    does not calculate the totals or decide whether the status is acceptable.
    """

    status: str
    tolerance: float
    total_outflow: float
    total_inflow: float
    diff: float
    per_type: dict[str, dict[str, float]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class DatasetManifest(BaseModel):
    """Describe dataset identity, handling metadata, and reported quality.

    The manifest records the dataset name, source and license labels, raw
    content hash, schema version, row count, PII flags, quality metrics, and an
    optional reconciliation report. ``created_at`` defaults to the current
    UTC-aware ISO-8601 timestamp. The manifest carries these declarations; it
    does not verify source authority, license validity, content identity, or
    the supplied quality assessment.
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
