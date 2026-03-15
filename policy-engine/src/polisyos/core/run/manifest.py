from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef, EnvInfo, ProducerInfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None

    producer: ProducerInfo | None = None
    env: EnvInfo | None = None

    registry_bundle: ArtifactRef

    inputs: list[ArtifactRef] = Field(default_factory=list)
    outputs: list[ArtifactRef] = Field(default_factory=list)

    status: str = "running"
    errors: list[dict[str, Any]] = Field(default_factory=list)

    trace_ref: ArtifactRef | None = None
    tenant_id: str | None = Field(
        default=None,
        description="Tenant identifier for tenant-scoped runs.",
    )
    cell_id: str | None = Field(
        default=None,
        description="Cell identifier for tenant-scoped runs.",
    )
    seed: int | None = Field(
        default=None,
        description="Deterministic seed for replayable runs.",
    )
    parent_run_id: str | None = Field(
        default=None,
        description="Parent run id for replay/resume lineage.",
    )
    replay_source_ref: ArtifactRef | None = Field(
        default=None,
        description="Original DecisionPacket reference when this run is a replay.",
    )
    execution_profile: str | None = Field(
        default=None,
        description="Effective execution profile used for this run.",
    )
    control_job_id: str | None = Field(
        default=None,
        description="Durable control-plane job identifier that launched this run.",
    )
    capability_manifest_ref: ArtifactRef | None = Field(
        default=None,
        description="Capability manifest captured for the run runtime posture.",
    )
    environment_manifest_ref: ArtifactRef | None = Field(
        default=None,
        description="Captured environment manifest reference.",
    )
    sbom_ref: ArtifactRef | None = Field(
        default=None,
        description="SBOM artifact reference captured for deployment provenance.",
    )
    tee_attestation_ref: ArtifactRef | None = Field(
        default=None,
        description="TEE attestation artifact reference for confidential execution.",
    )
