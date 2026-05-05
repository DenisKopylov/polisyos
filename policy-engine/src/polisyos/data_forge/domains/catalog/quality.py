"""Read-only catalog benchmark, QC, and readiness report contracts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel

from .shadow import CatalogShadowBundle, load_catalog_shadow_bundle


class CatalogBenchmarkReport(DataForgeModel):
    """Read-only summary of a catalog benchmark report."""

    path: str = Field(min_length=1)
    metrics: dict[str, object] = Field(default_factory=dict)


class CatalogQCReport(DataForgeModel):
    """Read-only summary of a catalog QC report."""

    path: str = Field(min_length=1)
    metrics: dict[str, object] = Field(default_factory=dict)
    passed: bool | None = None
    failed_checks: tuple[str, ...] = Field(default_factory=tuple)


class CatalogReadinessPackage(DataForgeModel):
    """Catalog readiness package assembled from published outputs."""

    root: str = Field(min_length=1)
    benchmark: CatalogBenchmarkReport
    qc: CatalogQCReport
    shadow: CatalogShadowBundle
    artifact_hashes: dict[str, str] = Field(default_factory=dict)

    @property
    def consumer_ready(self) -> bool:
        """Return whether published catalog artifacts are ready for consumers."""
        return self.shadow.consumer_ready and self.qc.passed is not False


def load_catalog_benchmark_report(path_or_root: str | Path) -> CatalogBenchmarkReport:
    """Load a catalog benchmark report without importing legacy code."""
    path = _resolve_report_path(path_or_root, "benchmark_report.json")
    payload = _read_json(path)
    return CatalogBenchmarkReport(path=str(path), metrics=_dict_value(payload.get("metrics")))


def load_catalog_qc_report(path_or_root: str | Path) -> CatalogQCReport:
    """Load a catalog QC report without importing legacy code."""
    path = _resolve_report_path(path_or_root, "qc_report.json")
    payload = _read_json(path)
    return CatalogQCReport(
        path=str(path),
        metrics=_dict_value(payload.get("metrics")),
        passed=_optional_bool(payload.get("passed")),
        failed_checks=_failed_checks(payload),
    )


def load_catalog_readiness_package(root: str | Path) -> CatalogReadinessPackage:
    """Load catalog readiness, benchmark, QC, and artifact hashes."""
    root_path = Path(root)
    shadow = load_catalog_shadow_bundle(root_path)
    return CatalogReadinessPackage(
        root=str(root_path),
        benchmark=load_catalog_benchmark_report(root_path),
        qc=load_catalog_qc_report(root_path),
        shadow=shadow,
        artifact_hashes={
            artifact.relative_path: artifact.observed_sha256
            for artifact in shadow.artifacts
            if artifact.observed_sha256 is not None
        },
    )


def _resolve_report_path(path_or_root: str | Path, report_name: str) -> Path:
    path = Path(path_or_root)
    return path / report_name if path.is_dir() else path


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return {str(key): value for key, value in payload.items()}


def _dict_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _failed_checks(payload: dict[str, object]) -> tuple[str, ...]:
    explicit = payload.get("failed_checks")
    if isinstance(explicit, list | tuple):
        return tuple(str(item) for item in explicit)
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return ()
    failed: list[str] = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        passed = item.get("passed")
        status = str(item.get("status") or "")
        if passed is False or status.lower() in {"fail", "failed", "error"}:
            failed.append(str(item.get("name") or item.get("check") or "unknown"))
    return tuple(failed)


__all__ = [
    "CatalogBenchmarkReport",
    "CatalogQCReport",
    "CatalogReadinessPackage",
    "load_catalog_benchmark_report",
    "load_catalog_qc_report",
    "load_catalog_readiness_package",
]
