"""Typed calibration-gate reports for Phase 1 microsimulation workflows."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import ConfigDict, Field

from polisyos.ir.kernel.base import KernelModel

if TYPE_CHECKING:
    from polisyos.ir.artifacts.contracts import ArtifactStore
    from polisyos.ir.artifacts.refs import InputRef
    from polisyos.ir.refs import MicrosimCalibrationReportRef


class MicrosimCalibrationReport(KernelModel):
    """Persisted readiness gate emitted by microsim calibration methods."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    artifact_name: Literal["microsim_calibration_report_v1.json"] = (
        "microsim_calibration_report_v1.json"
    )
    decision: Literal["pass", "warn", "block"]
    can_run_microsim: bool
    compatibility_status: str
    reason_code: str | None = None
    exact_feasible: bool = False
    distance_to_feasibility: float = Field(ge=0.0)
    normalized_distance: float = Field(ge=0.0)
    jacobian_rank: int | None = Field(default=None, ge=0)
    condition_number: float | None = Field(default=None, ge=0.0)
    max_abs_gap: float = Field(default=0.0, ge=0.0)
    warnings: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_microsim_calibration_report(
    *,
    compatibility_status: str,
    reason_code: str | None = None,
    exact_feasible: bool = False,
    distance_to_feasibility: float = 0.0,
    normalized_distance: float = 0.0,
    jacobian_rank: int | None = None,
    condition_number: float | None = None,
    max_abs_gap: float = 0.0,
    warnings: list[str] | None = None,
    blocking_reasons: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MicrosimCalibrationReport:
    """Construct a readiness report from the calibration compatibility surface."""

    decision, can_run_microsim = _decision_from_status(compatibility_status)
    resolved_warnings = [str(item).strip() for item in warnings or () if str(item).strip()]
    resolved_blocking = [str(item).strip() for item in blocking_reasons or () if str(item).strip()]
    if decision == "warn" and f"compatibility:{compatibility_status}" not in resolved_warnings:
        resolved_warnings.append(f"compatibility:{compatibility_status}")
    if decision == "block" and not resolved_blocking:
        resolved_blocking.append(f"compatibility:{compatibility_status}")
    return MicrosimCalibrationReport(
        decision=decision,
        can_run_microsim=can_run_microsim,
        compatibility_status=str(compatibility_status),
        reason_code=None if reason_code is None else str(reason_code),
        exact_feasible=bool(exact_feasible),
        distance_to_feasibility=max(float(distance_to_feasibility), 0.0),
        normalized_distance=max(float(normalized_distance), 0.0),
        jacobian_rank=jacobian_rank,
        condition_number=condition_number,
        max_abs_gap=max(float(max_abs_gap), 0.0),
        warnings=resolved_warnings,
        blocking_reasons=resolved_blocking,
        metadata=dict(metadata or {}),
    )


def report_from_target_compatibility(
    compatibility: Any,
    *,
    max_abs_gap: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> MicrosimCalibrationReport:
    """Map a reweighting compatibility payload into the persisted Phase 1 gate."""

    status = _enum_string(getattr(compatibility, "status", None), default="inconclusive")
    reason_code = _enum_string(getattr(compatibility, "reason_code", None))
    warnings = list(getattr(compatibility, "warnings", ()) or ())
    blocking_reasons: list[str] = []
    if status in {"incompatible", "inconclusive", "numeric_failure"}:
        blocking_reasons.append(f"compatibility:{status}")
    payload = dict(metadata or {})
    test_method = _enum_string(getattr(compatibility, "test_method", None))
    if test_method is not None:
        payload.setdefault("test_method", test_method)
    statistic = getattr(compatibility, "statistic", None)
    if statistic is not None:
        payload.setdefault("statistic", float(statistic))
    df = getattr(compatibility, "df", None)
    if df is not None:
        payload.setdefault("df", int(df))
    p_value = getattr(compatibility, "p_value", None)
    if p_value is not None:
        payload.setdefault("p_value", float(p_value))
    return build_microsim_calibration_report(
        compatibility_status=status,
        reason_code=reason_code,
        exact_feasible=bool(getattr(compatibility, "exact_feasible", False)),
        distance_to_feasibility=float(getattr(compatibility, "distance_to_feasibility", 0.0) or 0.0),
        normalized_distance=float(getattr(compatibility, "normalized_distance", 0.0) or 0.0),
        jacobian_rank=getattr(compatibility, "jacobian_rank", None),
        condition_number=getattr(compatibility, "condition_number", None),
        max_abs_gap=float(max_abs_gap),
        warnings=warnings,
        blocking_reasons=blocking_reasons,
        metadata=payload,
    )


def persist_microsim_calibration_report(
    store: "ArtifactStore",
    report: MicrosimCalibrationReport,
    *,
    inputs: list["InputRef"] | None = None,
    schema_name: str = "ir.microsim_calibration_report",
    schema_version: str = "1.0",
) -> "MicrosimCalibrationReportRef":
    """Persist a calibration gate report and return its typed ref."""

    from polisyos.ir.artifacts.io import put_json_artifact
    from polisyos.ir.canon import CanonSpec
    from polisyos.ir.refs import MicrosimCalibrationReportRef

    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.microsim_calibration_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return MicrosimCalibrationReportRef.model_validate(ref)


def load_microsim_calibration_report(
    store: "ArtifactStore",
    ref: "MicrosimCalibrationReportRef",
) -> MicrosimCalibrationReport:
    """Load a persisted calibration gate report."""

    from polisyos.ir.artifacts.io import get_json_artifact

    payload = get_json_artifact(store, ref.artifact_id)
    return MicrosimCalibrationReport.model_validate(payload)


def _decision_from_status(status: str) -> tuple[Literal["pass", "warn", "block"], bool]:
    normalized = str(status).strip().lower()
    if normalized == "compatible":
        return "pass", True
    if normalized == "approximately_compatible":
        return "warn", True
    return "block", False


def _enum_string(value: Any, *, default: str | None = None) -> str | None:
    if value is None:
        return default
    enum_value = getattr(value, "value", value)
    text = str(enum_value).strip()
    return text or default


__all__ = [
    "MicrosimCalibrationReport",
    "build_microsim_calibration_report",
    "load_microsim_calibration_report",
    "persist_microsim_calibration_report",
    "report_from_target_compatibility",
]
