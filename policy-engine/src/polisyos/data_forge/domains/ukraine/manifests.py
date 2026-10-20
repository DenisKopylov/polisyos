"""Manifest models and JSON helpers for the Ukraine Part B build stack."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.contracts import DataSnapshotRef
from polisyos.data_forge._ukraine_release_contracts import (
    D5ReleaseContentRef,
    D5ReleaseHandoffRequest,
    D5ReleaseProducerFacts,
)
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


class PytestCasePhaseReport(BaseModel):
    """One pytest setup, call, or teardown result for a collected node."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    node_id: str = Field(..., min_length=1)
    when: Literal["setup", "call", "teardown"]
    outcome: Literal["passed", "failed", "skipped", "xpassed"]
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_nonpass_reason(self) -> PytestCasePhaseReport:
        """Keep the actual reason for every non-passing phase in the typed receipt."""

        if self.outcome in {"failed", "skipped", "xpassed"} and not (self.reason or "").strip():
            raise ValueError("non-passing pytest phase requires its reason")
        return self


class PartAGateCollectionContext(BaseModel):
    """Admitted pytest collection profile, source set, and selection controls for C7."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    profile: Literal["policyos.ukraine.c7.collection.v1"]
    plugin_autoload: Literal["disabled"]
    pluggy_version: str = Field(..., min_length=1)
    ambient_controls: Literal["sanitized"]
    hook_capture: Literal["before_collection_modifyitems"]
    pytest_arguments: list[str] = Field(..., min_length=1)
    approved_pytest_addopts: list[str] = Field(default_factory=list)
    repo_plugin_source_digests: dict[str, str] = Field(..., min_length=1)
    keyword_expression: str = ""
    mark_expression: str = ""
    collect_only: bool = False
    deselected_node_ids: list[str] = Field(default_factory=list)
    ignored_paths: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_digest_map(self) -> PartAGateCollectionContext:
        """Reject unrooted source identities and malformed content digests."""

        for source_id, digest in self.repo_plugin_source_digests.items():
            prefix, separator, relative_path = source_id.partition(":")
            if (
                not separator
                or prefix not in {"workspace", "code"}
                or not relative_path
                or relative_path.startswith("/")
                or "\\" in relative_path
                or any(part in {"", ".", ".."} for part in relative_path.split("/"))
            ):
                raise ValueError("C7 collection source path is not a rooted relative identity")
            if (
                not digest.startswith("sha256:")
                or len(digest) != 71
                or any(character not in "0123456789abcdef" for character in digest[7:])
            ):
                raise ValueError("C7 collection source digest is malformed")
        return self

    @property
    def full_collection(self) -> bool:
        """Return true only for the admitted unfiltered C7 collection profile."""

        return (
            not self.keyword_expression
            and not self.mark_expression
            and not self.collect_only
            and not self.deselected_node_ids
            and not self.ignored_paths
            and len(self.approved_pytest_addopts) <= 1
            and all(option.startswith("--junitxml=") for option in self.approved_pytest_addopts)
        )


class PartAGateExecutionReceipt(BaseModel):
    """Content-bound collection and same-child pytest phase evidence for C7."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.ukraine.part_a_gate_execution.v2"] = (
        "policyos.ukraine.part_a_gate_execution.v2"
    )
    attempt_id: str = Field(..., pattern=r"^[0-9a-f]{32}$")
    test_path: str = Field(..., min_length=1)
    source_sha256: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    pytest_version: str = Field(..., min_length=1)
    config_path: str = Field(..., min_length=1)
    config_sha256: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    collection_context: PartAGateCollectionContext
    node_ids: list[str] = Field(..., min_length=1)
    phase_reports: list[PytestCasePhaseReport] = Field(default_factory=list)
    pytest_exit_status: int = Field(strict=True)
    workload_receipt_sha256: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    phases_receipt_sha256: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_phase_report_identity(self) -> PartAGateExecutionReceipt:
        """Reject duplicate node identities, phases, and reports outside collection."""

        if len(self.node_ids) != len(set(self.node_ids)):
            raise ValueError("C7 pytest receipt contains duplicate collected node IDs")
        known_node_ids = set(self.node_ids)
        phase_keys = [(item.node_id, item.when) for item in self.phase_reports]
        if any(node_id not in known_node_ids for node_id, _ in phase_keys):
            raise ValueError("C7 pytest receipt contains a phase for an uncollected node")
        if len(phase_keys) != len(set(phase_keys)):
            raise ValueError("C7 pytest receipt contains duplicate node phase reports")
        return self

    @property
    def complete_lifecycle(self) -> bool:
        """Allow only pytest's real setup-skip/failure phase shape and completed teardown."""

        by_node: dict[str, dict[str, PytestCasePhaseReport]] = {}
        for report in self.phase_reports:
            by_node.setdefault(report.node_id, {})[report.when] = report
        if set(by_node) != set(self.node_ids):
            return False
        for node_id in self.node_ids:
            reports = by_node[node_id]
            setup = reports.get("setup")
            if setup is None or reports.get("teardown") is None:
                return False
            if setup.outcome == "passed":
                if "call" not in reports:
                    return False
            elif "call" in reports:
                return False
        return True

    @property
    def complete_pass(self) -> bool:
        """Return true only when the full admitted C7 collection passed every phase."""

        return (
            self.collection_context.full_collection
            and self.pytest_exit_status == 0
            and self.complete_lifecycle
            and all(item.outcome == "passed" for item in self.phase_reports)
        )

    @property
    def contains_skip(self) -> bool:
        """Return true when any observed pytest phase was skipped."""

        return any(item.outcome == "skipped" for item in self.phase_reports)

    @property
    def complete_skip(self) -> bool:
        """Return true for a complete, non-failing pytest skip with exit status zero."""

        return (
            self.collection_context.full_collection
            and self.pytest_exit_status == 0
            and self.complete_lifecycle
            and self.contains_skip
            and not self.contains_failure
        )

    @property
    def contains_failure(self) -> bool:
        """Return true when any phase failed or unexpectedly passed an xfail case."""

        return any(item.outcome in {"failed", "xpassed"} for item in self.phase_reports)


class PartAGateManifest(BaseModel):
    """Server-only manifest recording the Part A integration gate result."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: str = Field(..., min_length=1, max_length=120)
    command: list[str] = Field(default_factory=list)
    server_only: bool = True
    passed: bool = False
    skipped: bool = False
    execution_receipt: PartAGateExecutionReceipt | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_execution_receipt_for_pass(self) -> PartAGateManifest:
        """Keep a positive gate status inseparable from complete same-run evidence."""

        if self.passed != (self.status == "passed"):
            raise ValueError("Part A gate passed flag and status disagree")
        if self.skipped != (self.status == "skipped"):
            raise ValueError("Part A gate skipped flag and status disagree")
        if self.passed and (
            self.execution_receipt is None or not self.execution_receipt.complete_pass
        ):
            raise ValueError("Part A gate cannot pass without complete C7 phase evidence")
        if (
            self.skipped
            and self.execution_receipt is not None
            and not self.execution_receipt.complete_skip
        ):
            raise ValueError("Part A gate cannot report a C7 skip without complete skip evidence")
        return self


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
    "PartAGateCollectionContext",
    "PartAGateExecutionReceipt",
    "PartAGateManifest",
    "PytestCasePhaseReport",
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
