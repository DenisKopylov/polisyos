"""Read-only shadow reader for completed legacy academic pipeline artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import duckdb
from pydantic import Field

from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    skg_materialized_schema_identity,
    skg_schema_generation_basis,
)
from polisyos.data_forge.kernel._base import DataForgeModel
from polisyos.data_forge.kernel.io import sha256_file
from polisyos.data_forge.kernel.io.generation_basis import compare_generation_basis

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class AcademicShadowArtifact(DataForgeModel):
    """Academic artifact observed through a read-only Data Forge adapter."""

    path: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    declared_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    observed_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    exists: bool
    size_bytes: int | None = Field(default=None, ge=0)
    checksum_ok: bool | None = None


class AcademicStageManifest(DataForgeModel):
    """Summary of a legacy academic stage manifest."""

    path: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    status: str = Field(min_length=1)
    metrics: dict[str, object] = Field(default_factory=dict)


class AcademicReadinessSummary(DataForgeModel):
    """Consumer-facing academic readiness extracted from published artifacts."""

    consumer_ready: bool = False
    readiness: dict[str, object] = Field(default_factory=dict)
    benchmark_metrics: dict[str, object] = Field(default_factory=dict)
    qc_metrics: dict[str, object] = Field(default_factory=dict)
    failed_readiness_checks: tuple[str, ...] = Field(default_factory=tuple)


class AcademicShadowBundle(DataForgeModel):
    """Read-only summary of a completed legacy academic output directory."""

    root: str = Field(min_length=1)
    publish_manifest_path: str = Field(min_length=1)
    pipeline: str = "academic"
    consumer_ready: bool = False
    readiness: dict[str, object] = Field(default_factory=dict)
    benchmark_metrics: dict[str, object] = Field(default_factory=dict)
    qc_metrics: dict[str, object] = Field(default_factory=dict)
    readiness_summary: AcademicReadinessSummary = Field(default_factory=AcademicReadinessSummary)
    artifacts: tuple[AcademicShadowArtifact, ...] = Field(default_factory=tuple)
    stage_manifests: tuple[AcademicStageManifest, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)

    def artifact_by_relative_path(self, relative_path: str) -> AcademicShadowArtifact | None:
        """Return an artifact summary by relative path."""
        for artifact in self.artifacts:
            if artifact.relative_path == relative_path:
                return artifact
        return None


class AcademicShadowDiff(DataForgeModel):
    """Small differential report between two academic shadow bundles."""

    baseline_root: str
    candidate_root: str
    added_artifacts: tuple[str, ...] = Field(default_factory=tuple)
    removed_artifacts: tuple[str, ...] = Field(default_factory=tuple)
    changed_artifacts: tuple[str, ...] = Field(default_factory=tuple)
    readiness_changes: dict[str, tuple[object, object]] = Field(default_factory=dict)
    metric_deltas: dict[str, float] = Field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        """Return whether any artifact, readiness, or metric changed."""
        return bool(
            self.added_artifacts
            or self.removed_artifacts
            or self.changed_artifacts
            or self.readiness_changes
            or self.metric_deltas
        )


def load_academic_shadow_bundle(root: str | Path) -> AcademicShadowBundle:
    """Load a completed academic output directory without importing legacy code."""
    root_path = Path(root)
    manifest_path = root_path / "publish" / "manifest.json"
    manifest = _read_json(manifest_path)
    extra = _dict_value(manifest.get("extra"))
    readiness_report = _read_readiness_report(root_path, extra.get("readiness_report"))
    readiness = {
        **_dict_value(readiness_report.get("readiness")),
        **_dict_value(extra.get("readiness")),
    }
    warnings: list[str] = []
    schema_generation = compare_generation_basis(
        readiness_report.get("schema_generation"),
        current=skg_schema_generation_basis(),
    )
    recorded_schema_identity = readiness_report.get("materialized_schema_identity")
    current_schema_identity: str | None = None
    materialized_schema_current = False
    if schema_generation.is_current:
        try:
            current_schema_identity = skg_materialized_schema_identity(
                root_path / "graph" / "scholar_knowledge.duckdb"
            )
        except (duckdb.Error, OSError):
            current_schema_identity = None
        materialized_schema_current = (
            isinstance(recorded_schema_identity, str)
            and recorded_schema_identity == current_schema_identity
        )
    schema_generation_current = schema_generation.is_current and materialized_schema_current
    readiness["schema_generation_current"] = schema_generation_current
    readiness["consumer_ready"] = _bool_value(
        readiness.get("consumer_ready")
    ) and schema_generation_current
    if not schema_generation.is_current:
        warnings.append(
            "academic SKG schema generation drift: "
            f"status={schema_generation.status}; "
            f"recorded_generation={schema_generation.recorded_generation}; "
            f"current_generation={schema_generation.current_generation}; "
            f"recorded_rule_version={schema_generation.recorded_rule_version}; "
            f"current_rule_version={schema_generation.current_rule_version}"
        )
    elif not materialized_schema_current:
        status = "missing" if not isinstance(recorded_schema_identity, str) else "incompatible"
        warnings.append(
            "academic SKG schema generation drift: "
            f"status={status}; "
            f"recorded_generation={schema_generation.recorded_generation}; "
            f"current_generation={schema_generation.current_generation}; "
            f"recorded_rule_version={schema_generation.recorded_rule_version}; "
            f"current_rule_version={schema_generation.current_rule_version}; "
            f"recorded_schema_identity={recorded_schema_identity or 'unrecorded'}; "
            f"current_schema_identity={current_schema_identity or 'unreadable'}"
        )
    benchmark_metrics = _dict_value(
        readiness_report.get("benchmark_metrics"),
        readiness_report.get("metrics"),
    )
    qc_metrics = _dict_value(readiness_report.get("qc_metrics"))
    readiness_summary = AcademicReadinessSummary(
        consumer_ready=_bool_value(readiness.get("consumer_ready")),
        readiness=readiness,
        benchmark_metrics=benchmark_metrics,
        qc_metrics=qc_metrics,
        failed_readiness_checks=_failed_readiness_checks(readiness),
    )

    artifacts = tuple(
        _load_artifact(root_path, item, warnings)
        for item in _list_value(manifest.get("artifacts"))
        if isinstance(item, dict)
    )

    return AcademicShadowBundle(
        root=str(root_path),
        publish_manifest_path=str(manifest_path),
        pipeline=str(manifest.get("pipeline") or "academic"),
        consumer_ready=readiness_summary.consumer_ready,
        readiness=readiness,
        benchmark_metrics=benchmark_metrics,
        qc_metrics=qc_metrics,
        readiness_summary=readiness_summary,
        artifacts=artifacts,
        stage_manifests=_load_stage_manifests(root_path),
        warnings=tuple(warnings),
    )


def compare_academic_shadow_bundles(
    baseline: AcademicShadowBundle,
    candidate: AcademicShadowBundle,
) -> AcademicShadowDiff:
    """Compare two completed academic shadow bundles."""
    baseline_artifacts = {artifact.relative_path: artifact for artifact in baseline.artifacts}
    candidate_artifacts = {artifact.relative_path: artifact for artifact in candidate.artifacts}
    baseline_paths = set(baseline_artifacts)
    candidate_paths = set(candidate_artifacts)

    changed = []
    for relative_path in sorted(baseline_paths & candidate_paths):
        baseline_hash = _best_hash(baseline_artifacts[relative_path])
        candidate_hash = _best_hash(candidate_artifacts[relative_path])
        if baseline_hash != candidate_hash:
            changed.append(relative_path)

    return AcademicShadowDiff(
        baseline_root=baseline.root,
        candidate_root=candidate.root,
        added_artifacts=tuple(sorted(candidate_paths - baseline_paths)),
        removed_artifacts=tuple(sorted(baseline_paths - candidate_paths)),
        changed_artifacts=tuple(changed),
        readiness_changes=_readiness_changes(baseline, candidate),
        metric_deltas=_metric_deltas(baseline, candidate),
    )


def _load_artifact(
    root: Path,
    payload: dict[object, object],
    warnings: list[str],
) -> AcademicShadowArtifact:
    raw_path = str(payload.get("path") or "")
    resolved = _resolve_path(root, raw_path)
    relative_path = _relative_path(root, resolved)
    declared_sha256 = _optional_str(payload.get("sha256")) or None
    exists = resolved.exists()
    observed_sha256 = sha256_file(resolved) if exists else None
    checksum_ok = None
    size_bytes = None
    if exists:
        size_bytes = resolved.stat().st_size
    else:
        warnings.append(f"missing artifact: {raw_path}")
    if declared_sha256:
        checksum_ok = observed_sha256 == declared_sha256
        if checksum_ok is False:
            warnings.append(f"checksum mismatch: {relative_path}")

    return AcademicShadowArtifact(
        path=str(resolved),
        relative_path=relative_path,
        declared_sha256=declared_sha256,
        observed_sha256=observed_sha256,
        exists=exists,
        size_bytes=size_bytes,
        checksum_ok=checksum_ok,
    )


def _load_stage_manifests(root: Path) -> tuple[AcademicStageManifest, ...]:
    manifests_root = root / "manifests"
    if not manifests_root.exists():
        return ()
    stage_manifests: list[AcademicStageManifest] = []
    for path in sorted(manifests_root.glob("*.json")):
        payload = _read_optional_json(path)
        if payload.get("kind") != "stage":
            continue
        stage_manifests.append(
            AcademicStageManifest(
                path=str(path),
                stage=str(payload.get("stage") or path.stem),
                status=str(payload.get("status") or "unknown"),
                metrics=_dict_value(payload.get("metrics")),
            )
        )
    return tuple(stage_manifests)


def _read_readiness_report(root: Path, raw_path: object) -> dict[str, object]:
    if not raw_path:
        return {}
    path = _resolve_path(root, str(raw_path))
    return _read_optional_json(path)


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return {str(key): value for key, value in payload.items()}


def _read_optional_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return _read_json(path)


def _dict_value(value: object, fallback: object = None) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    if isinstance(fallback, dict):
        return {str(key): item for key, item in fallback.items()}
    return {}


def _list_value(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    return value


def _bool_value(value: object) -> bool:
    return value if isinstance(value, bool) else False


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _resolve_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return root / path


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _failed_readiness_checks(readiness: dict[str, object]) -> tuple[str, ...]:
    return tuple(
        sorted(
            key for key, value in readiness.items() if value is False and key != "consumer_ready"
        )
    )


def _best_hash(artifact: AcademicShadowArtifact) -> str | None:
    return artifact.observed_sha256 or artifact.declared_sha256


def _readiness_changes(
    baseline: AcademicShadowBundle,
    candidate: AcademicShadowBundle,
) -> dict[str, tuple[object, object]]:
    baseline_values: dict[str, object] = {
        "consumer_ready": baseline.readiness_summary.consumer_ready,
        "failed_readiness_checks": baseline.readiness_summary.failed_readiness_checks,
        **baseline.readiness_summary.readiness,
    }
    candidate_values: dict[str, object] = {
        "consumer_ready": candidate.readiness_summary.consumer_ready,
        "failed_readiness_checks": candidate.readiness_summary.failed_readiness_checks,
        **candidate.readiness_summary.readiness,
    }
    changes: dict[str, tuple[object, object]] = {}
    for key in sorted(set(baseline_values) | set(candidate_values)):
        old_value = baseline_values.get(key)
        new_value = candidate_values.get(key)
        if old_value != new_value:
            changes[key] = (old_value, new_value)
    return changes


def _metric_deltas(
    baseline: AcademicShadowBundle,
    candidate: AcademicShadowBundle,
) -> dict[str, float]:
    baseline_metrics = _bundle_numeric_metrics(baseline)
    candidate_metrics = _bundle_numeric_metrics(candidate)
    deltas: dict[str, float] = {}
    for key in sorted(set(baseline_metrics) | set(candidate_metrics)):
        old_value = baseline_metrics.get(key, 0.0)
        new_value = candidate_metrics.get(key, 0.0)
        if old_value != new_value:
            deltas[key] = new_value - old_value
    return deltas


def _bundle_numeric_metrics(bundle: AcademicShadowBundle) -> dict[str, float]:
    metrics: dict[str, float] = {}
    metrics.update(_flatten_numbers("benchmark", bundle.readiness_summary.benchmark_metrics))
    metrics.update(_flatten_numbers("qc", bundle.readiness_summary.qc_metrics))
    return metrics


def _flatten_numbers(prefix: str, value: object) -> dict[str, float]:
    if isinstance(value, bool):
        return {}
    if isinstance(value, int | float):
        return {prefix: float(value)}
    if isinstance(value, dict):
        result: dict[str, float] = {}
        for key, item in cast("dict[object, object]", value).items():
            result.update(_flatten_numbers(f"{prefix}.{key}", item))
        return result
    return {}


__all__ = [
    "AcademicReadinessSummary",
    "AcademicShadowArtifact",
    "AcademicShadowBundle",
    "AcademicShadowDiff",
    "AcademicStageManifest",
    "compare_academic_shadow_bundles",
    "load_academic_shadow_bundle",
]
