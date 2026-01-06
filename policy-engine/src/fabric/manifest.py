from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class CoverageMetrics(BaseModel):
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    region_coverage: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class QualityMetrics(BaseModel):
    missing_rate: float = Field(..., ge=0.0, le=1.0)
    duplicate_rate: float = Field(..., ge=0.0, le=1.0)
    outlier_rate: float = Field(..., ge=0.0, le=1.0)
    coverage: CoverageMetrics

    model_config = ConfigDict(extra="forbid")


class DatasetManifest(BaseModel):
    dataset_name: str
    source: str
    license: str
    raw_hash: str
    schema_version: str
    row_count: int
    pii_flags: Dict[str, bool]
    quality: QualityMetrics
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    model_config = ConfigDict(extra="forbid")
