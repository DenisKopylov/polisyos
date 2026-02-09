from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import content_hash


class JobSpec(BaseModel):
    job_kind: str = "legacy_program"
    program_ref: ArtifactRef | None = None
    exec_plan_ref: ArtifactRef | None = None
    state_snapshot_ref: ArtifactRef | None = None
    seed: int = 0
    mode: str = "dev"
    required_metrics: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    method_fqn: str | None = None
    method_version: str | None = None
    method_params: dict[str, Any] = Field(default_factory=dict)
    input_refs: dict[str, ArtifactRef] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_job_kind(self) -> "JobSpec":
        if self.job_kind not in {"legacy_program", "method"}:
            raise ValueError("job_kind must be either 'legacy_program' or 'method'")
        return self

    @property
    def is_legacy_jax(self) -> bool:
        return not self.is_method_job

    @property
    def is_method_job(self) -> bool:
        return self.job_kind == "method" or self.method_fqn is not None


class JobKey(BaseModel):
    value: str

    @staticmethod
    def from_spec(spec: JobSpec) -> "JobKey":
        payload_obj = spec.model_dump(mode="json", exclude_none=True)
        if spec.is_legacy_jax:
            payload_obj.pop("job_kind", None)
            for key in ("method_fqn", "method_version", "method_params", "input_refs"):
                payload_obj.pop(key, None)
        payload = json.dumps(payload_obj, sort_keys=True)
        digest = content_hash(payload)
        return JobKey(value=f"job:{digest}")


class JobResult(BaseModel):
    job_key: JobKey
    state_delta_ref: ArtifactRef | None = None
    metrics_ref: ArtifactRef | None = None
    environment_ref: ArtifactRef | None = None
    environment_fingerprint: str | None = None
    state_snapshot_ref: ArtifactRef | None = None
    simulation_results_ref: ArtifactRef | None = None
    method_result_ref: ArtifactRef | None = None
    method_evidence_ref: ArtifactRef | None = None
    final_state: Any | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
