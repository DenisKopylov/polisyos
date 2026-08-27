"""Runtime-safe read API for Ukraine demographic static-aging artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts as core_artifacts
from polisyos.data_forge.domains.ukraine.manifests import (  # noqa: TC001
    D5ReleaseHandoffRequest,
)

from ._lazy import lazy_dir, load_lazy_export

if TYPE_CHECKING:
    import numpy.typing as npt

    from polisyos.data_forge.domains.ukraine import UkraineDemographyArtifacts

_UKRAINE_DOMAIN = "polisyos.data_forge.domains.ukraine"
REAL_BACKTEST_BUNDLE_CONTRACT_FQN = (
    "polisyos.data_forge.domains.ukraine.contracts.RealBacktestBundleContract"
)
_EXPORTS = {
    "UKRAINE_ASSET_GROUP": _UKRAINE_DOMAIN,
    "UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_DEMOGRAPHY_PRIORS_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_DEMOGRAPHY_TARGETS_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_NORMALIZED_SOURCES_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_RAW_SOURCES_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_READINESS_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_SOURCE_CONFIG_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_STATIC_AGING_INPUTS_KEY": _UKRAINE_DOMAIN,
    "UkraineDemographyArtifacts": _UKRAINE_DOMAIN,
    "UkraineLexPreShardDiff": _UKRAINE_DOMAIN,
    "UkraineLexPreShardSummary": _UKRAINE_DOMAIN,
    "UkraineLexShardEntry": _UKRAINE_DOMAIN,
    "UkraineLexShardPassSummary": _UKRAINE_DOMAIN,
    "UkraineReadinessSummary": _UKRAINE_DOMAIN,
    "UkraineShadowArtifact": _UKRAINE_DOMAIN,
    "UkraineShadowBundle": _UKRAINE_DOMAIN,
    "UkraineShadowDiff": _UKRAINE_DOMAIN,
    "UkraineSourceSummary": _UKRAINE_DOMAIN,
    "ReleaseManifest": "polisyos.data_forge.domains.ukraine.manifests",
    "RealBacktestBundleContract": "polisyos.data_forge.domains.ukraine.contracts",
    "compare_lex_pre_shard_summaries": _UKRAINE_DOMAIN,
    "compare_ukraine_shadow_bundles": _UKRAINE_DOMAIN,
    "infer_lex_snapshot_label": _UKRAINE_DOMAIN,
    "lex_pre_shard_index": _UKRAINE_DOMAIN,
    "lex_pre_shard_pass_name": _UKRAINE_DOMAIN,
    "load_demography_artifacts": _UKRAINE_DOMAIN,
    "load_donor_pool": _UKRAINE_DOMAIN,
    "load_lex_pre_shard_summary": _UKRAINE_DOMAIN,
    "load_manifest": "polisyos.data_forge.domains.ukraine.manifests",
    "load_reconciled_targets": _UKRAINE_DOMAIN,
    "load_transition_priors": _UKRAINE_DOMAIN,
    "load_ukraine_shadow_bundle": _UKRAINE_DOMAIN,
}


class UkraineStageArtifactVerificationError(RuntimeError):
    """Raised when a Ukraine producer artifact cannot be content-bound fail closed."""


class VerifiedUkraineStageArtifact(BaseModel):
    """One producer output whose verified bytes were admitted into immutable storage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_path: str = Field(min_length=1)
    content_ref: core_artifacts.ArtifactRef
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    row_count: int | None = Field(default=None, ge=0)
    nnz: int | None = Field(default=None, ge=0)
    producer_artifact_id: str | None = None

    @model_validator(mode="after")
    def _content_ref_matches_verified_hash(self) -> VerifiedUkraineStageArtifact:
        if self.content_ref.artifact_id.hex != self.sha256:
            raise ValueError("content_ref does not match the verified output hash")
        return self


class VerifiedUkraineStageArtifacts(BaseModel):
    """Fail-closed receipt for one completed Ukraine producer stage.

    This receipt proves file identity and content binding only. It deliberately
    cannot stand in for Scientist governance or Foundry release acceptance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_forge.ukraine.verified_stage.v2"] = (
        "policyos.data_forge.ukraine.verified_stage.v2"
    )
    verification_rule_version: Literal["ukraine-stage-artifacts.v2"] = (
        "ukraine-stage-artifacts.v2"
    )
    stage_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: Literal["completed"] = "completed"
    finished_at: str = Field(min_length=1)
    manifest_source_path: str = Field(min_length=1)
    manifest_ref: core_artifacts.ArtifactRef
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance_ref: Literal[
        "polisyos.data_forge.domains.ukraine.manifests.BuildRunManifest"
    ] = "polisyos.data_forge.domains.ukraine.manifests.BuildRunManifest"
    authority_purpose: Literal["producer_artifact_receipt"] = "producer_artifact_receipt"
    stage_status_provenance: Literal["institutionally_supplied"] = "institutionally_supplied"
    path_scope_provenance: Literal["recomputed"] = "recomputed"
    content_binding_provenance: Literal["recomputed"] = "recomputed"
    authoritative_for: tuple[str, ...] = (
        "producer_artifact_identity",
        "producer_artifact_content_binding",
    )
    may_not_use_for: tuple[str, ...] = (
        "governance_admissibility",
        "release_acceptance",
        "legal_intervention_compilation",
        "method_validity",
    )
    outputs: dict[str, VerifiedUkraineStageArtifact] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _manifest_ref_matches_verified_hash(self) -> VerifiedUkraineStageArtifacts:
        if self.manifest_ref.artifact_id.hex != self.manifest_sha256:
            raise ValueError("manifest_ref does not match the verified manifest hash")
        return self


class VerifiedUkraineReleaseArtifact(BaseModel):
    """One D5 release file admitted into CAS after path and content verification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_path: str = Field(min_length=1)
    content_ref: core_artifacts.ArtifactRef
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)

    @model_validator(mode="after")
    def _content_ref_matches_verified_hash(self) -> VerifiedUkraineReleaseArtifact:
        if self.content_ref.artifact_id.hex != self.sha256:
            raise ValueError("content_ref does not match the verified release artifact hash")
        return self


class VerifiedUkraineReleaseArtifacts(BaseModel):
    """Non-authoritative admission receipt for a complete D5 release inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_forge.ukraine.verified_release.v1"] = (
        "policyos.data_forge.ukraine.verified_release.v1"
    )
    verification_rule_version: Literal["ukraine-release-artifacts.v1"] = (
        "ukraine-release-artifacts.v1"
    )
    stage_id: Literal["d5"] = "d5"
    declared_release_root: str = Field(min_length=1)
    manifest_source_path: str = Field(min_length=1)
    manifest_ref: core_artifacts.ArtifactRef
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_size_bytes: int = Field(ge=0)
    provenance_ref: Literal[
        "polisyos.data_forge.domains.ukraine.manifests.ReleaseManifest"
    ] = "polisyos.data_forge.domains.ukraine.manifests.ReleaseManifest"
    authority_purpose: Literal["non_authoritative_release_artifact_admission"] = (
        "non_authoritative_release_artifact_admission"
    )
    stage_declaration_provenance: Literal["institutionally_supplied"] = (
        "institutionally_supplied"
    )
    release_root_declaration_provenance: Literal["institutionally_supplied"] = (
        "institutionally_supplied"
    )
    path_scope_provenance: Literal["recomputed"] = "recomputed"
    content_binding_provenance: Literal["recomputed"] = "recomputed"
    authoritative_for: tuple[str, ...] = ()
    verified_for: tuple[str, ...] = (
        "producer_artifact_identity",
        "producer_artifact_content_binding",
    )
    may_not_use_for: tuple[str, ...] = (
        "governance_admissibility",
        "release_acceptance",
        "publication",
        "method_validity",
    )
    handoff_request: D5ReleaseHandoffRequest
    bundle_contents: dict[str, dict[str, VerifiedUkraineReleaseArtifact]] = Field(
        default_factory=dict
    )
    evidence: dict[str, VerifiedUkraineReleaseArtifact] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _manifest_ref_matches_verified_hash(self) -> VerifiedUkraineReleaseArtifacts:
        if self.manifest_ref.artifact_id.hex != self.manifest_sha256:
            raise ValueError("manifest_ref does not match the verified release manifest hash")
        if self.authoritative_for:
            raise ValueError("release admission receipt cannot declare downstream authority")
        if set(self.verified_for) != {
            "producer_artifact_identity",
            "producer_artifact_content_binding",
        }:
            raise ValueError("release admission receipt has an invalid evidence-band scope")
        if set(self.may_not_use_for) != {
            "governance_admissibility",
            "release_acceptance",
            "publication",
            "method_validity",
        }:
            raise ValueError("release admission receipt must retain every authority denial")
        return self


def load_verified_stage_artifacts(
    manifest_path: Path,
    *,
    store: core_artifacts.FileSystemCAS,
    allowed_root: Path,
    expected_stage: str,
    required_outputs: tuple[str, ...] = (),
) -> VerifiedUkraineStageArtifacts:
    """Resolve and recompute one completed Ukraine stage manifest.

    Args:
        manifest_path: Producer-emitted ``BuildRunManifest`` JSON path.
        store: CAS that receives the exact manifest and output bytes admitted.
        allowed_root: Root that must contain the manifest and every output.
        expected_stage: Exact stage identifier the consumer requested.
        required_outputs: Output basenames the consumer requires.

    Returns:
        A purpose-limited receipt whose output hashes and sizes were recomputed.

    Raises:
        UkraineStageArtifactVerificationError: If any admission check fails.
    """
    from polisyos.data_forge.domains.ukraine.manifests import ArtifactRecord, BuildRunManifest

    root = allowed_root.resolve()
    resolved_manifest = _resolve_within_root(
        manifest_path,
        root=root,
        label="manifest",
    )
    try:
        manifest_bytes = resolved_manifest.read_bytes()
    except OSError as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to read stage manifest {resolved_manifest}: {exc}"
        ) from exc
    try:
        manifest = BuildRunManifest.model_validate_json(manifest_bytes)
    except Exception as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to parse stage manifest {resolved_manifest}: {exc}"
        ) from exc

    stage_id = str(manifest.stage_id.value)
    if stage_id != expected_stage:
        raise UkraineStageArtifactVerificationError(
            f"stage mismatch: expected {expected_stage}, received {stage_id}"
        )
    if manifest.status != "completed":
        raise UkraineStageArtifactVerificationError(
            f"stage status must be completed, received {manifest.status}"
        )

    validated_outputs: dict[str, tuple[Path, bytes, ArtifactRecord]] = {}
    for output in manifest.outputs:
        output_path = _resolve_within_root(Path(output.path), root=root, label="output")
        output_name = output_path.name
        if output_name in validated_outputs:
            raise UkraineStageArtifactVerificationError(
                f"duplicate output basename in stage manifest: {output_name}"
            )
        if not output.sha256:
            raise UkraineStageArtifactVerificationError(
                f"output is missing a declared content hash: {output_name}"
            )
        try:
            output_bytes = output_path.read_bytes()
        except OSError as exc:
            raise UkraineStageArtifactVerificationError(
                f"failed to read stage output {output_name}: {exc}"
            ) from exc
        recomputed_sha256 = _sha256_bytes(output_bytes)
        if recomputed_sha256 != output.sha256:
            raise UkraineStageArtifactVerificationError(
                f"content hash mismatch for output {output_name}"
            )
        recomputed_size = len(output_bytes)
        if recomputed_size != output.size_bytes:
            raise UkraineStageArtifactVerificationError(
                f"content size mismatch for output {output_name}"
            )
        validated_outputs[output_name] = (output_path, output_bytes, output)

    required = {name.strip() for name in required_outputs if name.strip()}
    missing = sorted(required.difference(validated_outputs))
    if missing:
        raise UkraineStageArtifactVerificationError(
            "required stage outputs are missing: " + ",".join(missing)
        )

    manifest_ref = store.put_bytes(
        manifest_bytes,
        core_artifacts.PutOptions(
            kind="data_forge.ukraine.stage_manifest_snapshot",
            media_type="application/json",
            schema=core_artifacts.SchemaInfo(
                name="polisyos.data_forge.ukraine.BuildRunManifest",
                version="1.0",
            ),
        ),
    )
    verified_outputs: dict[str, VerifiedUkraineStageArtifact] = {}
    for output_name, (output_path, output_bytes, output_record) in validated_outputs.items():
        content_ref = store.put_bytes(
            output_bytes,
            core_artifacts.PutOptions(
                kind="data_forge.ukraine.stage_output_snapshot",
                media_type=_snapshot_media_type(output_path),
            ),
        )
        verified_outputs[output_name] = VerifiedUkraineStageArtifact(
            source_path=str(output_path),
            content_ref=content_ref,
            sha256=_sha256_bytes(output_bytes),
            size_bytes=len(output_bytes),
            row_count=output_record.row_count,
            nnz=output_record.nnz,
            producer_artifact_id=output_record.artifact_id,
        )

    return VerifiedUkraineStageArtifacts(
        stage_id=stage_id,
        run_id=manifest.run_id,
        finished_at=manifest.finished_at,
        manifest_source_path=str(resolved_manifest),
        manifest_ref=manifest_ref,
        manifest_sha256=_sha256_bytes(manifest_bytes),
        outputs=verified_outputs,
    )


def load_verified_stage_output_bytes(
    store: core_artifacts.FileSystemCAS,
    receipt: VerifiedUkraineStageArtifacts,
    output_name: str,
) -> bytes:
    """Read one admitted output from CAS without reopening its producer path.

    Args:
        store: CAS containing the output snapshot named by the receipt.
        receipt: Verified stage receipt produced by :func:`load_verified_stage_artifacts`.
        output_name: Exact output basename to read.

    Returns:
        The immutable bytes admitted during stage verification.

    Raises:
        UkraineStageArtifactVerificationError: If the output is absent or its
            stored bytes no longer match the receipt.
    """

    output = receipt.outputs.get(output_name)
    if output is None:
        raise UkraineStageArtifactVerificationError(
            f"verified receipt lacks required output: {output_name}"
        )
    try:
        output_bytes = store.get_bytes(output.content_ref.artifact_id)
    except Exception as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to read admitted stage output {output_name}: {exc}"
        ) from exc
    if len(output_bytes) != output.size_bytes:
        raise UkraineStageArtifactVerificationError(
            f"admitted content size mismatch for output {output_name}"
        )
    if _sha256_bytes(output_bytes) != output.sha256:
        raise UkraineStageArtifactVerificationError(
            f"admitted content hash mismatch for output {output_name}"
        )
    return output_bytes


def load_verified_release_artifacts(
    manifest_path: Path,
    *,
    store: core_artifacts.FileSystemCAS,
    allowed_root: Path,
    expected_stage: str,
) -> VerifiedUkraineReleaseArtifacts:
    """Admit the exact D5 manifest, bundle files, and evidence files into CAS.

    The producer's stage and release-root fields remain institutional
    declarations. Path containment, file-set completeness, hashes, sizes, and
    CAS identity are recomputed by this boundary and cannot authorize release.

    Args:
        manifest_path: Producer-emitted ``ReleaseManifest`` path.
        store: CAS receiving the exact bytes read during admission.
        allowed_root: Root containing every declared release path.
        expected_stage: Stage requested by the downstream consumer.

    Returns:
        A frozen, purpose-limited receipt for the admitted release bytes.

    Raises:
        UkraineStageArtifactVerificationError: If any declaration is missing,
            malformed, out of scope, incomplete, or content-drifted.
    """

    from polisyos.data_forge.domains.ukraine.manifests import (
        ArtifactRecord,
        D5ReleaseContentRef,
        D5ReleaseHandoffRequest,
        ReleaseManifest,
    )

    required_evidence = {
        "cell_registry",
        "d4_governance_request",
        "d5_release_handoff_request",
        "graph_compression_bundle",
    }
    root = allowed_root.resolve()
    resolved_manifest = _resolve_within_root(manifest_path, root=root, label="manifest")
    try:
        manifest_bytes = resolved_manifest.read_bytes()
    except OSError as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to read release manifest {resolved_manifest}: {exc}"
        ) from exc
    try:
        manifest = ReleaseManifest.model_validate_json(manifest_bytes)
    except Exception as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to parse release manifest {resolved_manifest}: {exc}"
        ) from exc
    if set(manifest.evidence_refs) != required_evidence:
        raise UkraineStageArtifactVerificationError(
            "release manifest evidence_refs must match the exact D5 set"
        )
    if set(manifest.bundles) != set(manifest.bundle_contents):
        raise UkraineStageArtifactVerificationError(
            "release bundle declarations and content inventories must match exactly"
        )

    read_cache: dict[Path, bytes] = {}

    def _read_record(
        record: ArtifactRecord,
        *,
        label: str,
        containing_directory: Path | None = None,
    ) -> tuple[Path, bytes]:
        resolved = _resolve_within_root(Path(record.path), root=root, label=label)
        if containing_directory is not None and not resolved.is_relative_to(containing_directory):
            raise UkraineStageArtifactVerificationError(
                f"{label} path escapes declared bundle directory: {resolved}"
            )
        if not record.sha256:
            raise UkraineStageArtifactVerificationError(
                f"{label} is missing a declared content hash"
            )
        if resolved not in read_cache:
            try:
                read_cache[resolved] = resolved.read_bytes()
            except OSError as exc:
                raise UkraineStageArtifactVerificationError(
                    f"failed to read {label} {resolved}: {exc}"
                ) from exc
        payload = read_cache[resolved]
        if _sha256_bytes(payload) != record.sha256:
            raise UkraineStageArtifactVerificationError(f"content hash mismatch for {label}")
        if len(payload) != record.size_bytes:
            raise UkraineStageArtifactVerificationError(f"content size mismatch for {label}")
        return resolved, payload

    verified_bundle_bytes: dict[str, dict[str, tuple[Path, bytes]]] = {}
    for bundle_name, bundle_record in manifest.bundles.items():
        bundle_root = _resolve_directory_within_root(
            Path(bundle_record.path), root=root, label=f"bundle {bundle_name}"
        )
        declared_files: dict[str, tuple[Path, bytes]] = {}
        for relative_name, record in manifest.bundle_contents[bundle_name].items():
            declared_files[relative_name] = _read_record(
                record,
                label=f"bundle file {bundle_name}:{relative_name}",
                containing_directory=bundle_root,
            )
            declared_path = declared_files[relative_name][0]
            if declared_path.relative_to(bundle_root).as_posix() != relative_name:
                raise UkraineStageArtifactVerificationError(
                    f"bundle inventory key does not match its path for {bundle_name}"
                )
        actual_paths = {
            candidate.resolve()
            for candidate in bundle_root.rglob("*")
            if candidate.is_file()
        }
        declared_paths = {path for path, _payload in declared_files.values()}
        if actual_paths != declared_paths:
            raise UkraineStageArtifactVerificationError(
                f"bundle file inventory mismatch for {bundle_name}"
            )
        if sum(len(payload) for _path, payload in declared_files.values()) != (
            bundle_record.size_bytes
        ):
            raise UkraineStageArtifactVerificationError(
                f"bundle content size mismatch for {bundle_name}"
            )
        verified_bundle_bytes[bundle_name] = declared_files

    verified_evidence_bytes = {
        name: _read_record(record, label=f"release evidence {name}")
        for name, record in manifest.evidence_refs.items()
    }
    _handoff_path, handoff_bytes = verified_evidence_bytes["d5_release_handoff_request"]
    try:
        handoff = D5ReleaseHandoffRequest.model_validate_json(handoff_bytes)
    except Exception as exc:
        raise UkraineStageArtifactVerificationError(f"invalid D5 release handoff: {exc}") from exc
    if handoff.declared_stage != expected_stage:
        raise UkraineStageArtifactVerificationError(
            f"release stage mismatch: expected {expected_stage}, received {handoff.declared_stage}"
        )
    declared_release_root = _resolve_directory_within_root(
        Path(handoff.declared_release_root), root=root, label="declared release root"
    )
    if declared_release_root != resolved_manifest.parent:
        raise UkraineStageArtifactVerificationError(
            "declared release root does not contain the release manifest"
        )
    expected_handoff_refs = {
        name: D5ReleaseContentRef.from_artifact_record(record)
        for name, record in manifest.evidence_refs.items()
        if name != "d5_release_handoff_request"
    }
    if handoff.content_refs != expected_handoff_refs:
        raise UkraineStageArtifactVerificationError(
            "handoff content_refs must equal manifest evidence_refs without the handoff envelope"
        )

    def _persist(path: Path, payload: bytes, *, kind: str) -> VerifiedUkraineReleaseArtifact:
        content_ref = store.put_bytes(
            payload,
            core_artifacts.PutOptions(
                kind=kind,
                media_type=_snapshot_media_type(path),
            ),
        )
        return VerifiedUkraineReleaseArtifact(
            source_path=str(path),
            content_ref=content_ref,
            sha256=_sha256_bytes(payload),
            size_bytes=len(payload),
        )

    manifest_ref = store.put_bytes(
        manifest_bytes,
        core_artifacts.PutOptions(
            kind="data_forge.ukraine.release_manifest_snapshot",
            media_type="application/json",
            schema=core_artifacts.SchemaInfo(
                name="polisyos.data_forge.ukraine.ReleaseManifest",
                version="1.0",
            ),
        ),
    )
    verified_bundles = {
        bundle_name: {
            relative_name: _persist(
                path,
                payload,
                kind="data_forge.ukraine.release_bundle_file_snapshot",
            )
            for relative_name, (path, payload) in files.items()
        }
        for bundle_name, files in verified_bundle_bytes.items()
    }
    verified_evidence = {
        name: _persist(
            path,
            payload,
            kind=(
                "data_forge.ukraine.release_handoff_snapshot"
                if name == "d5_release_handoff_request"
                else "data_forge.ukraine.release_evidence_snapshot"
            ),
        )
        for name, (path, payload) in verified_evidence_bytes.items()
    }
    return VerifiedUkraineReleaseArtifacts(
        stage_id="d5",
        declared_release_root=str(declared_release_root),
        manifest_source_path=str(resolved_manifest),
        manifest_ref=manifest_ref,
        manifest_sha256=_sha256_bytes(manifest_bytes),
        manifest_size_bytes=len(manifest_bytes),
        handoff_request=handoff,
        bundle_contents=verified_bundles,
        evidence=verified_evidence,
    )


def load_verified_release_artifact_bytes(
    store: core_artifacts.FileSystemCAS,
    artifact: VerifiedUkraineReleaseArtifact,
) -> bytes:
    """Read and recheck one admitted D5 file from CAS only."""

    try:
        payload = store.get_bytes(artifact.content_ref.artifact_id)
    except Exception as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to read admitted release artifact: {exc}"
        ) from exc
    if len(payload) != artifact.size_bytes:
        raise UkraineStageArtifactVerificationError("admitted release artifact size mismatch")
    if _sha256_bytes(payload) != artifact.sha256:
        raise UkraineStageArtifactVerificationError("admitted release artifact hash mismatch")
    return payload


def _resolve_within_root(path: Path, *, root: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise UkraineStageArtifactVerificationError(f"{label} path is unavailable: {path}") from exc
    if not resolved.is_relative_to(root):
        raise UkraineStageArtifactVerificationError(
            f"{label} path escapes allowed root: {resolved}"
        )
    if not resolved.is_file():
        raise UkraineStageArtifactVerificationError(f"{label} path is not a file: {resolved}")
    return resolved


def _resolve_directory_within_root(path: Path, *, root: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise UkraineStageArtifactVerificationError(f"{label} path is unavailable: {path}") from exc
    if not resolved.is_relative_to(root):
        raise UkraineStageArtifactVerificationError(
            f"{label} path escapes allowed root: {resolved}"
        )
    if not resolved.is_dir():
        raise UkraineStageArtifactVerificationError(f"{label} path is not a directory: {resolved}")
    return resolved


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _snapshot_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".parquet":
        return "application/vnd.apache.parquet"
    if suffix == ".csv":
        return "text/csv"
    return "application/octet-stream"


def __getattr__(name: str) -> object:
    """Lazily resolve Ukraine exports without importing domain internals at module import."""
    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())


def __dir__() -> list[str]:
    """Return public Ukraine read_api names without resolving exports."""
    return lazy_dir(globals(), _EXPORTS)


def build_static_aging_state(
    *,
    base_weights: npt.ArrayLike,
    origin_state_index: npt.ArrayLike,
    artifacts: UkraineDemographyArtifacts,
    exit_weights: npt.ArrayLike | None = None,
    microsim_calibration_report: object | None = None,
    microsim_calibration_report_ref: object | None = None,
) -> dict[str, object]:
    """Compose a Foundry-ready state dict for static aging from read_api artifacts."""

    from polisyos.data_forge.domains.ukraine.static_aging import (
        build_static_aging_state as _build_static_aging_state,
    )

    return _build_static_aging_state(
        base_weights=base_weights,
        origin_state_index=origin_state_index,
        artifacts=artifacts,
        exit_weights=exit_weights,
        microsim_calibration_report=microsim_calibration_report,
        microsim_calibration_report_ref=microsim_calibration_report_ref,
    )


__all__ = sorted(
    (
        *_EXPORTS,
        "REAL_BACKTEST_BUNDLE_CONTRACT_FQN",
        "UkraineStageArtifactVerificationError",
        "VerifiedUkraineReleaseArtifact",
        "VerifiedUkraineReleaseArtifacts",
        "VerifiedUkraineStageArtifact",
        "VerifiedUkraineStageArtifacts",
        "build_static_aging_state",
        "load_verified_stage_output_bytes",
        "load_verified_stage_artifacts",
        "load_verified_release_artifact_bytes",
        "load_verified_release_artifacts",
    )
)
