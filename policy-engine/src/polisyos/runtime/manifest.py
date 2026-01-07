from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ArtifactRef(BaseModel):
    artifact_type: str
    path: str
    media_type: str
    schema_version: Optional[str] = None
    step: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    model_config = ConfigDict(extra="forbid")


class RunManifest(BaseModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    run_id: str
    parent_run_id: Optional[str] = None
    status: str = "running"
    started_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    finished_at: Optional[str] = None
    generator: Dict[str, str] = Field(default_factory=dict)
    budgets: Dict[str, float] = Field(default_factory=dict)
    budget_usage: Dict[str, float] = Field(default_factory=dict)
    pruning_reason: Optional[Dict[str, Any]] = None
    artifacts: List[ArtifactRef] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
