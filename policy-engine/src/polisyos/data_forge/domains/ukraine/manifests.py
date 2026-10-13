"""Manifest models and JSON helpers for the Ukraine Part B build stack."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.data_forge.domains.ukraine.models import StageId
from polisyos.data_forge.kernel.io import sha256_file

if TYPE_CHECKING:
    from pathlib import Path


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""

    return datetime.now(UTC).isoformat()


class DirectoryTreeEntry(BaseModel):
    """One regular file in a content-bound source directory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_index: int = Field(ge=0)
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


def directory_tree_entries(path: Path, *, artifact_index: int = 0) -> list[DirectoryTreeEntry]:
    """Hash the complete portable regular-file set beneath one source directory."""
    if path.is_symlink():
        raise ValueError(f"source directory is a symlink: {path}")
    root = path.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"source path is not a directory: {path}")
    entries: list[DirectoryTreeEntry] = []
    for item in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        if item.is_symlink():
            raise ValueError(f"source directory contains a symlink: {item}")
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValueError(f"source directory contains a non-regular entry: {item}")
        payload = item.read_bytes()
        entries.append(
            DirectoryTreeEntry(
                artifact_index=artifact_index,
                relative_path=item.relative_to(root).as_posix(),
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
            )
        )
    if not entries:
        raise ValueError(f"source directory has no regular files: {path}")
    return entries


def directory_tree_sha256(entries: list[DirectoryTreeEntry]) -> str:
    """Return a stable digest for a complete, ordered directory entry set."""
    payload = [item.model_dump(mode="json") for item in entries]
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
        if path.is_symlink():
            raise ValueError(f"artifact path is a symlink: {path}")
        sha256 = ""
        size_bytes = 0
        if path.exists() and path.is_file():
            # Preserve established single-file identity exactly.
            sha256 = sha256_file(path)
            size_bytes = int(path.stat().st_size)
        elif path.exists() and path.is_dir():
            entries = directory_tree_entries(path)
            sha256 = directory_tree_sha256(entries)
            size_bytes = sum(item.size_bytes for item in entries)
        return cls(
            path=str(path),
            sha256=sha256,
            size_bytes=size_bytes,
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


_VALIDATION_FINDING_MESSAGE_MAX_LENGTH: int | None = ValidationFinding.model_json_schema()[
    "properties"
]["message"].get("maxLength")


def _make_validation_finding(*, severity: str, code: str, message: str) -> ValidationFinding:
    """Project producer-authored text to the finding DTO's display limit.

    This factory is for internally generated display messages only. Direct DTO
    construction and validation of supplied payloads remain strict.
    """

    max_length = _VALIDATION_FINDING_MESSAGE_MAX_LENGTH
    if max_length is not None and max_length > 0 and len(message) > max_length:
        marker = "…"
        if max_length <= len(marker):
            message = message[:max_length]
        else:
            retained_length = max_length - len(marker)
            prefix_length = (retained_length + 1) // 2
            suffix_length = retained_length - prefix_length
            suffix = message[-suffix_length:] if suffix_length else ""
            message = f"{message[:prefix_length]}{marker}{suffix}"
    return ValidationFinding(severity=severity, code=code, message=message)


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
    raw_tree_entries: list[DirectoryTreeEntry] = Field(default_factory=list)
    endpoint: str | None = None
    notes: list[str] = Field(default_factory=list)


class HouseholdDiagnosticPanelBasis(BaseModel):
    """Candidate-only source basis for the D3 household diagnostic panel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_forge.household_diagnostic_basis.v1"] = (
        "policyos.data_forge.household_diagnostic_basis.v1"
    )
    status: Literal["complete", "incomplete"]
    authority_purpose: Literal["candidate_diagnostic"] = "candidate_diagnostic"
    source_id: Literal["household_microdata"] = "household_microdata"
    raw_directory: ArtifactRecord | None = None
    raw_tree_entries: list[DirectoryTreeEntry] = Field(default_factory=list)
    source_snapshot_manifest_path: str | None = None
    source_snapshot_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    normalized_manifest_path: str | None = None
    normalized_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    normalized_artifact: ArtifactRecord | None = None
    source_snapshot_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_row_count: int = Field(ge=0)
    source_record_hashes: list[str] = Field(default_factory=list)
    panel_artifact: ArtifactRecord
    raw_tree_provenance: Literal["recomputed"] = "recomputed"
    snapshot_binding_provenance: Literal["recomputed"] = "recomputed"
    normalized_content_provenance: Literal["recomputed"] = "recomputed"
    row_lineage_provenance: Literal["recomputed"] = "recomputed"
    panel_transform_provenance: Literal["recomputed"] = "recomputed"
    population_coverage_provenance: Literal["not_established"] = "not_established"
    custody_provenance: Literal["not_established"] = "not_established"
    currentness_provenance: Literal["not_established"] = "not_established"
    representativeness_provenance: Literal["not_established"] = "not_established"
    production_unit_provenance: Literal["not_established"] = "not_established"
    production_time_provenance: Literal["not_established"] = "not_established"
    unresolved_assumptions: list[str] = Field(
        default_factory=lambda: [
            "population_coverage",
            "custody",
            "currentness",
            "representativeness",
            "production_unit",
            "production_time",
        ]
    )


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
    data_snapshot_ref: DataSnapshotRef | None = None
    input_bindings_artifact_id: str | None = None
    validation: list[ValidationFinding] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_data_snapshot_ref(self) -> RuntimeBundleManifest:
        """Keep the typed selected view coherent with its legacy artifact ID."""
        ref = self.data_snapshot_ref
        if ref is None:
            return self
        if ref.kind != "fabric.data_snapshot" or ref.media_type != "application/json":
            raise ValueError("runtime bundle DataSnapshot ref has the wrong artifact contract")
        if self.data_snapshot_artifact_id is not None and (
            self.data_snapshot_artifact_id != str(ref.artifact_id)
        ):
            raise ValueError("runtime bundle DataSnapshot ref differs from its artifact ID")
        return self


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
    handoff_rule_version: Literal["ukraine-d5-release-handoff.v1"] = "ukraine-d5-release-handoff.v1"
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
