"""Run manifest schema persisted for completed, replayed, and tenant-scoped executions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..artifacts.manifest import ArtifactRef, EnvInfo, ProducerInfo


def utc_now() -> datetime:
    """Return a second-granularity UTC timestamp for stable run-manifest defaults."""
    return datetime.now(UTC).replace(microsecond=0)


class RunManifest(BaseModel):
    """Canonical summary of one executable run, its provenance, and its produced artifacts."""

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


class RunOwnerSnapshot(BaseModel):
    """Immutable, selected-profile owner facts needed to resume an incomplete run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0.1"]
    run_manifest: RunManifest
    access_scope_sha256: str | None
    previous_snapshot_ref: ArtifactRef | None

    @field_validator("access_scope_sha256")
    @classmethod
    def _validate_scope_digest(cls, value: str | None) -> str | None:
        """Keep absent scope explicit and reject malformed supplied digests."""
        if value is not None and (
            not isinstance(value, str)
            or len(value) != 71
            or not value.startswith("sha256:")
            or any(char not in "0123456789abcdef" for char in value[7:])
        ):
            raise ValueError("access_scope_sha256 must be sha256:<64 lowercase hex>")
        return value
