"""Public fabric manifest module API."""
from datetime import datetime, timezone
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class CoverageMetrics(BaseModel):
    """Coverage metrics data model."""
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    region_coverage: Optional[str] = None

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
    per_type: Dict[str, Dict[str, float]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class DatasetManifest(BaseModel):
    """Dataset manifest data model."""
    dataset_name: str
    source: str
    license: str
    raw_hash: str
    schema_version: str
    row_count: int
    pii_flags: Dict[str, bool]
    quality: QualityMetrics
    reconciliation: Optional[ReconciliationReport] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = ConfigDict(extra="forbid")
