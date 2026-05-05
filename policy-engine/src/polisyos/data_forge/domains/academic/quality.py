"""Read-only academic benchmark and QC report contracts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel

from .shadow import AcademicShadowBundle, load_academic_shadow_bundle


class AcademicBenchmarkReport(DataForgeModel):
    """Read-only summary of an academic benchmark report."""

    path: str = Field(min_length=1)
    metrics: dict[str, object] = Field(default_factory=dict)
    readiness: dict[str, object] = Field(default_factory=dict)
    passed: bool | None = None
    failed_checks: tuple[str, ...] = Field(default_factory=tuple)


class AcademicQCReport(DataForgeModel):
    """Read-only summary of an academic QC report."""

    path: str = Field(min_length=1)
    metrics: dict[str, object] = Field(default_factory=dict)
    passed: bool | None = None
    failed_checks: tuple[str, ...] = Field(default_factory=tuple)


class AcademicReadinessPackage(DataForgeModel):
    """Academic readiness package assembled from legacy publish outputs."""

    root: str = Field(min_length=1)
    benchmark: AcademicBenchmarkReport
    qc: AcademicQCReport
    shadow: AcademicShadowBundle
    artifact_hashes: dict[str, str] = Field(default_factory=dict)

    @property
    def consumer_ready(self) -> bool:
        """Return whether published artifacts are ready for read-only consumers."""
        return (
            self.shadow.consumer_ready
            and self.benchmark.passed is not False
            and self.qc.passed is not False
        )


def load_academic_benchmark_report(path_or_root: str | Path) -> AcademicBenchmarkReport:
    """Load an academic benchmark report without importing legacy code."""
    path = _resolve_report_path(path_or_root, "benchmark_report.json")
    payload = _read_json(path)
    readiness = _dict_value(payload.get("readiness"))
    return AcademicBenchmarkReport(
        path=str(path),
        metrics=_dict_value(payload.get("metrics")),
        readiness=readiness,
        passed=_optional_bool(readiness.get("passed")),
        failed_checks=_string_tuple(readiness.get("failed_checks")),
    )


def load_academic_qc_report(path_or_root: str | Path) -> AcademicQCReport:
    """Load an academic QC report without importing legacy code."""
    path = _resolve_report_path(path_or_root, "qc_report.json")
    payload = _read_json(path)
    return AcademicQCReport(
        path=str(path),
        metrics=_dict_value(payload.get("metrics")),
        passed=_optional_bool(payload.get("passed")),
        failed_checks=_qc_failed_checks(payload),
    )


def load_academic_readiness_package(root: str | Path) -> AcademicReadinessPackage:
    """Load academic readiness, benchmark, QC, and artifact hash summaries."""
    root_path = Path(root)
    shadow = load_academic_shadow_bundle(root_path)
    return AcademicReadinessPackage(
        root=str(root_path),
        benchmark=load_academic_benchmark_report(root_path),
        qc=load_academic_qc_report(root_path),
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


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item) for item in value)


def _qc_failed_checks(payload: dict[str, object]) -> tuple[str, ...]:
    explicit = _string_tuple(payload.get("failed_checks"))
    if explicit:
        return explicit
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
    "AcademicBenchmarkReport",
    "AcademicQCReport",
    "AcademicReadinessPackage",
    "load_academic_benchmark_report",
    "load_academic_qc_report",
    "load_academic_readiness_package",
]
