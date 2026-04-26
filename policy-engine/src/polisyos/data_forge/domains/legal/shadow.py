"""Read-only shadow bridge for completed legacy Lex batch artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel
from polisyos.data_forge.kernel.io import sha256_file

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class LegalShadowArtifact(DataForgeModel):
    """Legacy Lex artifact observed through a read-only Data Forge adapter."""

    path: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    declared_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    observed_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    exists: bool
    size_bytes: int | None = Field(default=None, ge=0)
    checksum_ok: bool | None = None


class LegalStageManifest(DataForgeModel):
    """Summary of a legacy Lex stage manifest."""

    path: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    status: str = Field(min_length=1)
    metrics: dict[str, object] = Field(default_factory=dict)
    artifact_count: int = Field(ge=0)


class LegalShadowBundle(DataForgeModel):
    """Read-only summary of a completed legacy Lex output directory."""

    root: str = Field(min_length=1)
    publish_manifest_path: str = Field(min_length=1)
    pipeline: str = "lex"
    published_at: str | None = None
    artifacts: tuple[LegalShadowArtifact, ...] = Field(default_factory=tuple)
    consumer_ready: bool = False
    release_ready: bool = False
    consumer_readiness: dict[str, object] = Field(default_factory=dict)
    release_readiness: dict[str, object] = Field(default_factory=dict)
    quality_summary: dict[str, object] = Field(default_factory=dict)
    benchmark_summary: dict[str, object] = Field(default_factory=dict)
    table_counts: dict[str, int] = Field(default_factory=dict)
    stage_manifests: tuple[LegalStageManifest, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)

    def artifact_by_relative_path(self, relative_path: str) -> LegalShadowArtifact | None:
        """Return an artifact summary by relative path."""
        for artifact in self.artifacts:
            if artifact.relative_path == relative_path:
                return artifact
        return None


class LegalShadowDiff(DataForgeModel):
    """Small differential report between two legal shadow bundles."""

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


def load_lex_shadow_bundle(root: str | Path) -> LegalShadowBundle:
    """Load a completed legacy Lex output directory without importing Lex batch code."""
    root_path = Path(root)
    publish_manifest_path = root_path / "publish" / "manifest.json"
    manifest = _read_json(publish_manifest_path)
    consumer_readiness = _read_optional_json(root_path / "publish" / "consumer_readiness.json")
    release_readiness = _dict_value(consumer_readiness.get("release_readiness"))
    quality_summary = _dict_value(consumer_readiness.get("quality_summary"))
    benchmark_summary = _dict_value(consumer_readiness.get("benchmark_summary"))
    table_counts = _int_dict(consumer_readiness.get("table_counts"))
    readiness = _dict_value(consumer_readiness.get("readiness"))

    warnings: list[str] = []
    artifacts = tuple(
        _load_artifact(root_path, item, warnings)
        for item in _list_value(manifest.get("artifacts"))
        if isinstance(item, dict)
    )

    consumer_ready = _bool_value(readiness.get("consumer_ready"), consumer_readiness.get("ready"))
    release_ready = _bool_value(release_readiness.get("release_ready"), consumer_ready)

    return LegalShadowBundle(
        root=str(root_path),
        publish_manifest_path=str(publish_manifest_path),
        pipeline=str(manifest.get("pipeline") or "lex"),
        published_at=_optional_str(manifest.get("published_at")),
        artifacts=artifacts,
        consumer_ready=consumer_ready,
        release_ready=release_ready,
        consumer_readiness=consumer_readiness,
        release_readiness=release_readiness,
        quality_summary=quality_summary,
        benchmark_summary=benchmark_summary,
        table_counts=table_counts,
        stage_manifests=_load_stage_manifests(root_path),
        warnings=tuple(warnings),
    )


def compare_lex_shadow_bundles(
    baseline: LegalShadowBundle,
    candidate: LegalShadowBundle,
) -> LegalShadowDiff:
    """Compare two completed legacy Lex shadow bundles."""
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

    readiness_changes: dict[str, tuple[object, object]] = {}
    for name in ("consumer_ready", "release_ready"):
        old_value = getattr(baseline, name)
        new_value = getattr(candidate, name)
        if old_value != new_value:
            readiness_changes[name] = (old_value, new_value)

    return LegalShadowDiff(
        baseline_root=baseline.root,
        candidate_root=candidate.root,
        added_artifacts=tuple(sorted(candidate_paths - baseline_paths)),
        removed_artifacts=tuple(sorted(baseline_paths - candidate_paths)),
        changed_artifacts=tuple(changed),
        readiness_changes=readiness_changes,
        metric_deltas=_metric_deltas(baseline, candidate),
    )


def _load_artifact(
    root: Path,
    payload: dict[object, object],
    warnings: list[str],
) -> LegalShadowArtifact:
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

    return LegalShadowArtifact(
        path=str(resolved),
        relative_path=relative_path,
        declared_sha256=declared_sha256,
        observed_sha256=observed_sha256,
        exists=exists,
        size_bytes=size_bytes,
        checksum_ok=checksum_ok,
    )


def _load_stage_manifests(root: Path) -> tuple[LegalStageManifest, ...]:
    manifests_root = root / "manifests"
    if not manifests_root.exists():
        return ()
    stage_manifests: list[LegalStageManifest] = []
    for path in sorted(manifests_root.glob("*.json")):
        payload = _read_optional_json(path)
        if payload.get("kind") != "stage":
            continue
        stage_manifests.append(
            LegalStageManifest(
                path=str(path),
                stage=str(payload.get("stage") or path.stem),
                status=str(payload.get("status") or "unknown"),
                metrics=_dict_value(payload.get("metrics")),
                artifact_count=len(_list_value(payload.get("artifacts"))),
            )
        )
    return tuple(stage_manifests)


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


def _best_hash(artifact: LegalShadowArtifact) -> str | None:
    return artifact.observed_sha256 or artifact.declared_sha256


def _metric_deltas(
    baseline: LegalShadowBundle,
    candidate: LegalShadowBundle,
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


def _bundle_numeric_metrics(bundle: LegalShadowBundle) -> dict[str, float]:
    metrics: dict[str, float] = {}
    metrics.update(_flatten_numbers("table_counts", bundle.table_counts))
    metrics.update(_flatten_numbers("quality", bundle.quality_summary))
    metrics.update(_flatten_numbers("benchmark", bundle.benchmark_summary))
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
    "LegalShadowArtifact",
    "LegalShadowBundle",
    "LegalShadowDiff",
    "LegalStageManifest",
    "compare_lex_shadow_bundles",
    "load_lex_shadow_bundle",
]
