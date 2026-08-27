"""Manifest models and JSON helpers for the Ukraine Part B build stack."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.data_forge.domains.ukraine.models import StageId  # noqa: TC001
from polisyos.data_forge.kernel.io import sha256_file

if TYPE_CHECKING:
    from pathlib import Path


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""

    return datetime.now(UTC).isoformat()


class ArtifactRecord(BaseModel):
    """File metadata recorded in stage, bundle, and release manifests."""

    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str = ""
    size_bytes: int = 0
    row_count: int | None = None
    nnz: int | None = None
    artifact_id: str | None = None

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        row_count: int | None = None,
        nnz: int | None = None,
        artifact_id: str | None = None,
    ) -> ArtifactRecord:
        return cls(
            path=str(path),
            sha256=sha256_file(path) if path.exists() and path.is_file() else "",
            size_bytes=int(path.stat().st_size) if path.exists() and path.is_file() else 0,
            row_count=row_count,
            nnz=nnz,
            artifact_id=artifact_id,
        )


class ValidationFinding(BaseModel):
    """Machine-readable validation finding emitted by stage validators."""

    model_config = ConfigDict(extra="forbid")

    severity: str = Field(..., min_length=1, max_length=32)
    code: str = Field(..., min_length=1, max_length=120)
    message: str = Field(..., min_length=1, max_length=255)


class BuildRunManifest(BaseModel):
    """Top-level manifest emitted for every bootstrap, validation, and build stage."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., min_length=1, max_length=120)
    stage_id: StageId
    status: str = Field(..., min_length=1, max_length=120)
    started_at: str
    finished_at: str
    elapsed_s: float = 0.0
    peak_rss_gib: float = 0.0
    disk_used_gib: float = 0.0
    inputs: list[ArtifactRecord] = Field(default_factory=list)
    outputs: list[ArtifactRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    findings: list[ValidationFinding] = Field(default_factory=list)
    resume_from: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class SourceSnapshotManifest(BaseModel):
    """Manifest describing the discovered and fetched raw source snapshot."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1, max_length=120)
    adapter_id: str = Field(..., min_length=1, max_length=120)
    status: str = Field(..., min_length=1, max_length=120)
    discovered_at: str
    raw_artifacts: list[ArtifactRecord] = Field(default_factory=list)
    endpoint: str | None = None
    notes: list[str] = Field(default_factory=list)


class SkippedSourceManifest(BaseModel):
    """Manifest emitted for optional sources that were intentionally skipped."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1, max_length=120)
    reason: str = Field(..., min_length=1, max_length=255)
    skipped_at: str


class NormalizedArtifactManifest(BaseModel):
    """Manifest describing one normalized parquet output and its lineage fields."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1, max_length=120)
    stage_id: StageId
    status: str = Field(..., min_length=1, max_length=120)
    normalized_artifact: ArtifactRecord
    schema_version: str = Field(..., min_length=1, max_length=32)
    join_keys: list[str] = Field(default_factory=list)
    lineage_fields: list[str] = Field(default_factory=list)
    findings: list[ValidationFinding] = Field(default_factory=list)


class RuntimeBundleManifest(BaseModel):
    """Manifest describing runtime bundle outputs and loadability evidence."""

    model_config = ConfigDict(extra="forbid")

    artifact_name: str = "runtime_bundle_manifest.json"
    outputs: dict[str, ArtifactRecord] = Field(default_factory=dict)
    data_snapshot_artifact_id: str | None = None
    input_bindings_artifact_id: str | None = None
    validation: list[ValidationFinding] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class CalibrationBundleManifest(BaseModel):
    """Manifest describing calibration-plane outputs and contract bundle artifacts."""

    model_config = ConfigDict(extra="forbid")

    artifact_name: str = "calibration_bundle_manifest.json"
    outputs: dict[str, ArtifactRecord] = Field(default_factory=dict)
    validation: list[ValidationFinding] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ReleaseManifest(BaseModel):
    """Final release manifest with bundle hashes, lineage, and validation metrics."""

    model_config = ConfigDict(extra="forbid")

    artifact_name: str = "release_manifest_v1.json"
    bundles: dict[str, ArtifactRecord] = Field(default_factory=dict)
    bundle_contents: dict[str, dict[str, ArtifactRecord]] = Field(default_factory=dict)
    evidence_refs: dict[str, ArtifactRecord] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    validation: list[ValidationFinding] = Field(default_factory=list)
    lineage: dict[str, Any] = Field(default_factory=dict)


class D5ReleaseContentRef(BaseModel):
    """Content declaration embedded in the non-authoritative D5 handoff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)

    @classmethod
    def from_artifact_record(cls, record: ArtifactRecord) -> D5ReleaseContentRef:
        """Project a release artifact record into the narrow handoff contract."""

        return cls(path=record.path, sha256=record.sha256, size_bytes=record.size_bytes)


class D5ReleaseProducerFacts(BaseModel):
    """Candidate facts supplied by the D5 producer for downstream evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_region_id: str = Field(min_length=1, max_length=120)
    primary_sector_id: str = Field(min_length=1, max_length=120)
    graph_compression_degree_preservation_score: float = Field(ge=0.0, le=1.0)
    graph_compression_edge_weight_reconstruction_error: float = Field(ge=0.0)


class D5ReleaseHandoffRequest(BaseModel):
    """Purpose-limited candidate request from DataForge to the D5 consumer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_forge.ukraine.d5_release_handoff_request.v1"] = (
        "policyos.data_forge.ukraine.d5_release_handoff_request.v1"
    )
    handoff_rule_version: Literal["ukraine-d5-release-handoff.v1"] = (
        "ukraine-d5-release-handoff.v1"
    )
    authority_purpose: Literal["producer_release_handoff_request"] = (
        "producer_release_handoff_request"
    )
    provenance_ref: Literal[
        "polisyos.data_forge.domains.ukraine.builders.release.build_d5_stage"
    ] = "polisyos.data_forge.domains.ukraine.builders.release.build_d5_stage"
    declared_stage: Literal["d5"] = "d5"
    declared_release_root: str = Field(min_length=1)
    created_at: str = Field(default_factory=utc_now_iso, min_length=1)
    time_role: Literal["producer_handoff_created_at"] = "producer_handoff_created_at"
    capability_state: Literal["bridge_missing"] = "bridge_missing"
    consumer_state: Literal["consumer_missing"] = "consumer_missing"
    authoritative_for: tuple[str, ...] = ()
    may_not_use_for: tuple[str, ...] = (
        "legal_intervention_compilation",
        "governance_admissibility",
        "release_acceptance",
        "publication",
    )
    producer_facts: D5ReleaseProducerFacts
    content_refs: dict[str, D5ReleaseContentRef]

    @model_validator(mode="after")
    def _enforce_candidate_boundary(self) -> D5ReleaseHandoffRequest:
        required_refs = {
            "cell_registry",
            "d4_governance_request",
            "graph_compression_bundle",
        }
        if set(self.content_refs) != required_refs:
            raise ValueError("D5 handoff content_refs must match the exact release evidence set")
        if self.authoritative_for:
            raise ValueError("D5 producer handoff cannot declare downstream authority")
        required_denials = {
            "legal_intervention_compilation",
            "governance_admissibility",
            "release_acceptance",
            "publication",
        }
        if set(self.may_not_use_for) != required_denials:
            raise ValueError("D5 producer handoff must retain every authority denial")
        return self


class PartAGateManifest(BaseModel):
    """Server-only manifest recording the Part A integration gate result."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(..., min_length=1, max_length=120)
    command: list[str] = Field(default_factory=list)
    server_only: bool = True
    passed: bool = False
    skipped: bool = False
    created_at: str = Field(default_factory=utc_now_iso)
    notes: list[str] = Field(default_factory=list)


class ServerCapabilityManifest(BaseModel):
    """Capability manifest produced by the bootstrap capability probe."""

    model_config = ConfigDict(extra="forbid")

    host: str = Field(..., min_length=1, max_length=255)
    python_available: bool = False
    uv_available: bool = False
    duckdb_available: bool = False
    jax_available: bool = False
    lifelines_available: bool = False
    gdal_available: bool = False
    osmium_available: bool = False
    total_ram_gib: float = 0.0
    free_disk_gib: float = 0.0
    created_at: str = Field(default_factory=utc_now_iso)


def write_manifest(path: Path, payload: BaseModel) -> Path:
    """Write a manifest model to JSON with deterministic key ordering."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload.model_dump(mode="json"),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def load_manifest(path: Path, model_cls: type[BaseModel]) -> BaseModel:
    """Load a manifest from JSON into a typed pydantic model."""

    return model_cls.model_validate_json(path.read_text(encoding="utf-8"))


__all__ = [
    "ArtifactRecord",
    "BuildRunManifest",
    "CalibrationBundleManifest",
    "D5ReleaseContentRef",
    "D5ReleaseHandoffRequest",
    "D5ReleaseProducerFacts",
    "NormalizedArtifactManifest",
    "PartAGateManifest",
    "ReleaseManifest",
    "RuntimeBundleManifest",
    "ServerCapabilityManifest",
    "SkippedSourceManifest",
    "SourceSnapshotManifest",
    "ValidationFinding",
    "load_manifest",
    "utc_now_iso",
    "write_manifest",
]
