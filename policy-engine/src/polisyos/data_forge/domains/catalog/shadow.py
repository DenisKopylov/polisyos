"""Read-only shadow reader for completed legacy dataset catalog artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel
from polisyos.data_forge.kernel.io import sha256_file

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class CatalogShadowArtifact(DataForgeModel):
    """Catalog artifact observed through a read-only Data Forge adapter."""

    path: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    declared_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    observed_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    exists: bool
    size_bytes: int | None = Field(default=None, ge=0)
    checksum_ok: bool | None = None


class CatalogStageManifest(DataForgeModel):
    """Summary of a legacy catalog stage manifest."""

    path: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    status: str = Field(min_length=1)
    metrics: dict[str, object] = Field(default_factory=dict)


class CatalogSourceSummary(DataForgeModel):
    """Read-only source-level summary from a published catalog readiness artifact."""

    source_id: str = Field(min_length=1)
    family: str | None = None
    execution_tier: str | None = None
    run_lane: str | None = None
    dataset_count: int = Field(default=0, ge=0)
    observation_count: int = Field(default=0, ge=0)
    publish_blocking: bool = False
    ready: bool = False
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class CatalogReadinessSummary(DataForgeModel):
    """Consumer-facing catalog readiness extracted from published artifacts."""

    consumer_ready: bool = False
    full_publish_ready: bool = False
    publish_mode: str | None = None
    readiness: dict[str, object] = Field(default_factory=dict)
    table_counts: dict[str, int] = Field(default_factory=dict)
    benchmark_metrics: dict[str, object] = Field(default_factory=dict)
    failed_readiness_checks: tuple[str, ...] = Field(default_factory=tuple)


class CatalogShadowBundle(DataForgeModel):
    """Read-only summary of a completed legacy dataset catalog output directory."""

    root: str = Field(min_length=1)
    publish_manifest_path: str = Field(min_length=1)
    pipeline: str = "datasets"
    consumer_ready: bool = False
    full_publish_ready: bool = False
    publish_mode: str | None = None
    readiness: dict[str, object] = Field(default_factory=dict)
    table_counts: dict[str, int] = Field(default_factory=dict)
    benchmark_metrics: dict[str, object] = Field(default_factory=dict)
    readiness_summary: CatalogReadinessSummary = Field(default_factory=CatalogReadinessSummary)
    source_summaries: tuple[CatalogSourceSummary, ...] = Field(default_factory=tuple)
    artifacts: tuple[CatalogShadowArtifact, ...] = Field(default_factory=tuple)
    stage_manifests: tuple[CatalogStageManifest, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)

    def artifact_by_relative_path(self, relative_path: str) -> CatalogShadowArtifact | None:
        """Return an artifact summary by relative path."""
        for artifact in self.artifacts:
            if artifact.relative_path == relative_path:
                return artifact
        return None

    def source_by_id(self, source_id: str) -> CatalogSourceSummary | None:
        """Return a source summary by source id."""
        for source in self.source_summaries:
            if source.source_id == source_id:
                return source
        return None


class CatalogShadowDiff(DataForgeModel):
    """Small differential report between two catalog shadow bundles."""

    baseline_root: str
    candidate_root: str
    added_artifacts: tuple[str, ...] = Field(default_factory=tuple)
    removed_artifacts: tuple[str, ...] = Field(default_factory=tuple)
    changed_artifacts: tuple[str, ...] = Field(default_factory=tuple)
    added_sources: tuple[str, ...] = Field(default_factory=tuple)
    removed_sources: tuple[str, ...] = Field(default_factory=tuple)
    changed_sources: tuple[str, ...] = Field(default_factory=tuple)
    readiness_changes: dict[str, tuple[object, object]] = Field(default_factory=dict)
    metric_deltas: dict[str, float] = Field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        """Return whether any artifact, source, readiness, or metric changed."""
        return bool(
            self.added_artifacts
            or self.removed_artifacts
            or self.changed_artifacts
            or self.added_sources
            or self.removed_sources
            or self.changed_sources
            or self.readiness_changes
            or self.metric_deltas
        )


def load_catalog_shadow_bundle(root: str | Path) -> CatalogShadowBundle:
    """Load a completed catalog output directory without importing legacy code."""
    root_path = Path(root)
    manifest_path = root_path / "publish" / "manifest.json"
    manifest = _read_json(manifest_path)
    extra = _dict_value(manifest.get("extra"))
    consumer_readiness = _read_consumer_readiness(root_path, extra)
    readiness = _dict_value(consumer_readiness.get("readiness"))
    table_counts = _int_dict(consumer_readiness.get("table_counts"))
    benchmark_metrics = _dict_value(consumer_readiness.get("benchmark_metrics"))
    consumer_ready = _bool_value(extra.get("consumer_ready"), readiness.get("consumer_ready"))
    full_publish_ready = _bool_value(
        extra.get("full_publish_ready"),
        readiness.get("full_publish_ready"),
    )
    publish_mode = _optional_str(consumer_readiness.get("publish_mode"))
    readiness_summary = CatalogReadinessSummary(
        consumer_ready=consumer_ready,
        full_publish_ready=full_publish_ready,
        publish_mode=publish_mode,
        readiness=readiness,
        table_counts=table_counts,
        benchmark_metrics=benchmark_metrics,
        failed_readiness_checks=_failed_readiness_checks(readiness),
    )
    source_summaries = _source_summaries(consumer_readiness)

    warnings: list[str] = []
    artifacts = tuple(
        _load_artifact(root_path, item, warnings)
        for item in _list_value(manifest.get("artifacts"))
        if isinstance(item, dict)
    )

    return CatalogShadowBundle(
        root=str(root_path),
        publish_manifest_path=str(manifest_path),
        pipeline=str(manifest.get("pipeline") or "datasets"),
        consumer_ready=consumer_ready,
        full_publish_ready=full_publish_ready,
        publish_mode=publish_mode,
        readiness=readiness,
        table_counts=table_counts,
        benchmark_metrics=benchmark_metrics,
        readiness_summary=readiness_summary,
        source_summaries=source_summaries,
        artifacts=artifacts,
        stage_manifests=_load_stage_manifests(root_path),
        warnings=tuple(warnings),
    )


def compare_catalog_shadow_bundles(
    baseline: CatalogShadowBundle,
    candidate: CatalogShadowBundle,
) -> CatalogShadowDiff:
    """Compare two completed catalog shadow bundles."""
    baseline_artifacts = {artifact.relative_path: artifact for artifact in baseline.artifacts}
    candidate_artifacts = {artifact.relative_path: artifact for artifact in candidate.artifacts}
    baseline_paths = set(baseline_artifacts)
    candidate_paths = set(candidate_artifacts)

    changed_artifacts = []
    for relative_path in sorted(baseline_paths & candidate_paths):
        baseline_hash = _best_hash(baseline_artifacts[relative_path])
        candidate_hash = _best_hash(candidate_artifacts[relative_path])
        if baseline_hash != candidate_hash:
            changed_artifacts.append(relative_path)

    source_changes = _source_changes(baseline, candidate)
    return CatalogShadowDiff(
        baseline_root=baseline.root,
        candidate_root=candidate.root,
        added_artifacts=tuple(sorted(candidate_paths - baseline_paths)),
        removed_artifacts=tuple(sorted(baseline_paths - candidate_paths)),
        changed_artifacts=tuple(changed_artifacts),
        added_sources=source_changes[0],
        removed_sources=source_changes[1],
        changed_sources=source_changes[2],
        readiness_changes=_readiness_changes(baseline, candidate),
        metric_deltas=_metric_deltas(baseline, candidate),
    )


def _load_artifact(
    root: Path,
    payload: dict[object, object],
    warnings: list[str],
) -> CatalogShadowArtifact:
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

    return CatalogShadowArtifact(
        path=str(resolved),
        relative_path=relative_path,
        declared_sha256=declared_sha256,
        observed_sha256=observed_sha256,
        exists=exists,
        size_bytes=size_bytes,
        checksum_ok=checksum_ok,
    )


def _load_stage_manifests(root: Path) -> tuple[CatalogStageManifest, ...]:
    manifests_root = root / "manifests"
    if not manifests_root.exists():
        return ()
    stage_manifests: list[CatalogStageManifest] = []
    for path in sorted(manifests_root.glob("*.json")):
        payload = _read_optional_json(path)
        if payload.get("kind") != "stage":
            continue
        stage_manifests.append(
            CatalogStageManifest(
                path=str(path),
                stage=str(payload.get("stage") or path.stem),
                status=str(payload.get("status") or "unknown"),
                metrics=_dict_value(payload.get("metrics")),
            )
        )
    return tuple(stage_manifests)


def _read_consumer_readiness(root: Path, extra: dict[str, object]) -> dict[str, object]:
    raw_path = extra.get("consumer_readiness_manifest") or "publish/consumer_readiness.json"
    return _read_optional_json(_resolve_path(root, str(raw_path)))


def _source_summaries(payload: dict[str, object]) -> tuple[CatalogSourceSummary, ...]:
    summaries: list[CatalogSourceSummary] = []
    for item in _list_value(payload.get("source_summaries")):
        if not isinstance(item, dict):
            continue
        source = _dict_value(item)
        source_id = str(source.get("source_id") or source.get("name") or "").strip()
        if not source_id:
            continue
        summaries.append(
            CatalogSourceSummary(
                source_id=source_id,
                family=_optional_str(source.get("family")),
                execution_tier=_optional_str(source.get("execution_tier")),
                run_lane=_optional_str(source.get("run_lane")),
                dataset_count=_non_negative_int(source.get("dataset_count")),
                observation_count=_non_negative_int(source.get("observation_count")),
                publish_blocking=_bool_value(source.get("publish_blocking")),
                ready=_bool_value(source.get("ready")),
                warnings=tuple(str(value) for value in _list_value(source.get("warnings"))),
            )
        )
    return tuple(sorted(summaries, key=lambda source: source.source_id))


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return {str(key): value for key, value in payload.items()}


def _read_optional_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return _read_json(path)


def _dict_value(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _list_value(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    return value


def _int_dict(value: object) -> dict[str, int]:
    source = _dict_value(value)
    result: dict[str, int] = {}
    for key, item in source.items():
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            result[key] = item
    return result


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _bool_value(value: object, fallback: object = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(fallback, bool):
        return fallback
    return False


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
            key
            for key, value in readiness.items()
            if value is False and key not in {"consumer_ready", "full_publish_ready"}
        )
    )


def _best_hash(artifact: CatalogShadowArtifact) -> str | None:
    return artifact.observed_sha256 or artifact.declared_sha256


def _readiness_changes(
    baseline: CatalogShadowBundle,
    candidate: CatalogShadowBundle,
) -> dict[str, tuple[object, object]]:
    baseline_values: dict[str, object] = {
        "consumer_ready": baseline.readiness_summary.consumer_ready,
        "full_publish_ready": baseline.readiness_summary.full_publish_ready,
        "failed_readiness_checks": baseline.readiness_summary.failed_readiness_checks,
        "publish_mode": baseline.readiness_summary.publish_mode,
        **baseline.readiness_summary.readiness,
    }
    candidate_values: dict[str, object] = {
        "consumer_ready": candidate.readiness_summary.consumer_ready,
        "full_publish_ready": candidate.readiness_summary.full_publish_ready,
        "failed_readiness_checks": candidate.readiness_summary.failed_readiness_checks,
        "publish_mode": candidate.readiness_summary.publish_mode,
        **candidate.readiness_summary.readiness,
    }
    changes: dict[str, tuple[object, object]] = {}
    for key in sorted(set(baseline_values) | set(candidate_values)):
        old_value = baseline_values.get(key)
        new_value = candidate_values.get(key)
        if old_value != new_value:
            changes[key] = (old_value, new_value)
    return changes


def _source_changes(
    baseline: CatalogShadowBundle,
    candidate: CatalogShadowBundle,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    baseline_sources = {source.source_id: source for source in baseline.source_summaries}
    candidate_sources = {source.source_id: source for source in candidate.source_summaries}
    baseline_ids = set(baseline_sources)
    candidate_ids = set(candidate_sources)
    changed = []
    for source_id in sorted(baseline_ids & candidate_ids):
        if baseline_sources[source_id] != candidate_sources[source_id]:
            changed.append(source_id)
    return (
        tuple(sorted(candidate_ids - baseline_ids)),
        tuple(sorted(baseline_ids - candidate_ids)),
        tuple(changed),
    )


def _metric_deltas(
    baseline: CatalogShadowBundle,
    candidate: CatalogShadowBundle,
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


def _bundle_numeric_metrics(bundle: CatalogShadowBundle) -> dict[str, float]:
    metrics: dict[str, float] = {}
    metrics.update(_flatten_numbers("table_counts", bundle.readiness_summary.table_counts))
    metrics.update(_flatten_numbers("benchmark", bundle.readiness_summary.benchmark_metrics))
    for source in bundle.source_summaries:
        metrics[f"source.{source.source_id}.dataset_count"] = float(source.dataset_count)
        metrics[f"source.{source.source_id}.observation_count"] = float(source.observation_count)
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
    "CatalogReadinessSummary",
    "CatalogShadowArtifact",
    "CatalogShadowBundle",
    "CatalogShadowDiff",
    "CatalogSourceSummary",
    "CatalogStageManifest",
    "compare_catalog_shadow_bundles",
    "load_catalog_shadow_bundle",
]
