from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

from polisyos.core.artifacts.manifest import ArtifactRef


class JobSpec(BaseModel):
    program_ref: ArtifactRef
    exec_plan_ref: ArtifactRef | None = None
    state_snapshot_ref: ArtifactRef | None = None
    seed: int = 0
    mode: str = "dev"
    required_metrics: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class JobKey(BaseModel):
    value: str

    @staticmethod
    def from_spec(spec: JobSpec) -> "JobKey":
        payload = json.dumps(spec.model_dump(mode="json", exclude_none=True), sort_keys=True)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return JobKey(value=f"job:{digest}")


class JobResult(BaseModel):
    job_key: JobKey
    state_delta_ref: ArtifactRef | None = None
    metrics_ref: ArtifactRef | None = None
    state_snapshot_ref: ArtifactRef | None = None
    final_state: Any | None = None
    warnings: list[str] = Field(default_factory=list)
