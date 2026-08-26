"""Runtime-safe read API for Ukraine demographic static-aging artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

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
    """One recomputed producer output admitted through the Ukraine read boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    row_count: int | None = Field(default=None, ge=0)
    nnz: int | None = Field(default=None, ge=0)
    artifact_id: str | None = None


class VerifiedUkraineStageArtifacts(BaseModel):
    """Fail-closed receipt for one completed Ukraine producer stage.

    This receipt proves file identity and content binding only. It deliberately
    cannot stand in for Scientist governance or Foundry release acceptance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_forge.ukraine.verified_stage.v1"] = (
        "policyos.data_forge.ukraine.verified_stage.v1"
    )
    verification_rule_version: Literal["ukraine-stage-artifacts.v1"] = (
        "ukraine-stage-artifacts.v1"
    )
    stage_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: Literal["completed"] = "completed"
    finished_at: str = Field(min_length=1)
    manifest_path: str = Field(min_length=1)
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


def load_verified_stage_artifacts(
    manifest_path: Path,
    *,
    allowed_root: Path,
    expected_stage: str,
    required_outputs: tuple[str, ...] = (),
) -> VerifiedUkraineStageArtifacts:
    """Resolve and recompute one completed Ukraine stage manifest.

    Args:
        manifest_path: Producer-emitted ``BuildRunManifest`` JSON path.
        allowed_root: Root that must contain the manifest and every output.
        expected_stage: Exact stage identifier the consumer requested.
        required_outputs: Output basenames the consumer requires.

    Returns:
        A purpose-limited receipt whose output hashes and sizes were recomputed.

    Raises:
        UkraineStageArtifactVerificationError: If any admission check fails.
    """
    from polisyos.data_forge.domains.ukraine.manifests import BuildRunManifest, load_manifest

    root = allowed_root.resolve()
    resolved_manifest = _resolve_within_root(
        manifest_path,
        root=root,
        label="manifest",
    )
    try:
        manifest = load_manifest(resolved_manifest, BuildRunManifest)
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

    verified_outputs: dict[str, VerifiedUkraineStageArtifact] = {}
    for output in manifest.outputs:
        output_path = _resolve_within_root(Path(output.path), root=root, label="output")
        output_name = output_path.name
        if output_name in verified_outputs:
            raise UkraineStageArtifactVerificationError(
                f"duplicate output basename in stage manifest: {output_name}"
            )
        if not output.sha256:
            raise UkraineStageArtifactVerificationError(
                f"output is missing a declared content hash: {output_name}"
            )
        recomputed_sha256 = _sha256_file(output_path)
        if recomputed_sha256 != output.sha256:
            raise UkraineStageArtifactVerificationError(
                f"content hash mismatch for output {output_name}"
            )
        recomputed_size = int(output_path.stat().st_size)
        if recomputed_size != output.size_bytes:
            raise UkraineStageArtifactVerificationError(
                f"content size mismatch for output {output_name}"
            )
        verified_outputs[output_name] = VerifiedUkraineStageArtifact(
            path=str(output_path),
            sha256=recomputed_sha256,
            size_bytes=recomputed_size,
            row_count=output.row_count,
            nnz=output.nnz,
            artifact_id=output.artifact_id,
        )

    required = {name.strip() for name in required_outputs if name.strip()}
    missing = sorted(required.difference(verified_outputs))
    if missing:
        raise UkraineStageArtifactVerificationError(
            "required stage outputs are missing: " + ",".join(missing)
        )

    return VerifiedUkraineStageArtifacts(
        stage_id=stage_id,
        run_id=manifest.run_id,
        finished_at=manifest.finished_at,
        manifest_path=str(resolved_manifest),
        manifest_sha256=_sha256_file(resolved_manifest),
        outputs=verified_outputs,
    )


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        "VerifiedUkraineStageArtifact",
        "VerifiedUkraineStageArtifacts",
        "build_static_aging_state",
        "load_verified_stage_artifacts",
    )
)
