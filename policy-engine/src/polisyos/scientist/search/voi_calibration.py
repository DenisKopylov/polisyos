"""Calibration, regret and default-enable guards for VOI scheduling."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.search.voi_models import VOIRunReport, validate_mandatory_gate_policy


class VOIShadowBaselineComparison(BaseModel):
    """Compare VOI shadow scheduling against a static baseline."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    static_expected_cost: float = Field(ge=0.0)
    voi_expected_cost: float = Field(ge=0.0)
    static_safety_score: float = Field(ge=0.0, le=1.0)
    voi_safety_score: float = Field(ge=0.0, le=1.0)
    regret: float = Field(ge=0.0)
    non_worse_safety: bool
    cost_targeting_improved: bool
    explanation: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_explanation(self) -> VOIShadowBaselineComparison:
        if not self.explanation.strip():
            raise ValueError("VOI shadow comparison requires explanation")
        return self


class VOICalibrationReport(BaseModel):
    """Calibration status consumed before any default-enable request."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    comparison: VOIShadowBaselineComparison
    calibration_status: Literal["uncalibrated", "shadow", "calibrated", "blocked"]
    default_enable_allowed: bool
    blockers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def compare_voi_to_static_baseline(
    report: VOIRunReport,
    *,
    static_expected_cost: float,
    static_safety_score: float,
    voi_safety_score: float,
) -> VOIShadowBaselineComparison:
    """Build a deterministic shadow comparison for VOI vs static scheduling."""

    voi_expected_cost = report.total_expected_cost
    cost_targeting_improved = voi_expected_cost <= static_expected_cost
    non_worse_safety = voi_safety_score + 1e-9 >= static_safety_score
    regret = max(0.0, static_safety_score - voi_safety_score) + max(
        0.0,
        voi_expected_cost - static_expected_cost,
    )
    changed_cost = static_expected_cost - voi_expected_cost
    explanation = (
        "VOI shadow comparison is non-worse on safety and improves cost targeting."
        if non_worse_safety and cost_targeting_improved
        else "VOI shadow comparison is blocked until safety and cost targeting are non-worse."
    )
    return VOIShadowBaselineComparison(
        run_id=report.run_id,
        static_expected_cost=max(static_expected_cost, 0.0),
        voi_expected_cost=voi_expected_cost,
        static_safety_score=static_safety_score,
        voi_safety_score=voi_safety_score,
        regret=regret,
        non_worse_safety=non_worse_safety,
        cost_targeting_improved=cost_targeting_improved,
        explanation=explanation,
        metadata={
            "calibration_status": report.calibration_status,
            "decision_count": len(report.decisions),
            "expected_cost_delta": changed_cost,
        },
    )


def build_voi_calibration_report(
    report: VOIRunReport,
    *,
    comparison: VOIShadowBaselineComparison,
) -> VOICalibrationReport:
    """Summarize whether VOI is calibrated enough for advisory/default rollout."""

    blockers = validate_mandatory_gate_policy(report)
    if not comparison.non_worse_safety:
        blockers.append("safety_worse_than_static")
    if not comparison.cost_targeting_improved:
        blockers.append("cost_targeting_not_improved")
    if comparison.regret > 0.0:
        blockers.append("positive_shadow_regret")
    calibrated = not blockers
    return VOICalibrationReport(
        run_id=report.run_id,
        comparison=comparison,
        calibration_status="calibrated" if calibrated else "blocked",
        default_enable_allowed=calibrated,
        blockers=sorted(set(blockers)),
        metadata={"source_calibration_status": report.calibration_status},
    )


def validate_voi_default_enable(
    *,
    report: VOIRunReport,
    calibration_report: VOICalibrationReport | None = None,
    calibration_report_ref: ArtifactRef | None = None,
    regret_report_ref: ArtifactRef | None = None,
    learned_or_shadow: bool = True,
) -> list[str]:
    """Fail closed unless calibration/regret evidence supports default enable."""

    violations = validate_mandatory_gate_policy(report)
    if learned_or_shadow:
        if calibration_report_ref is None:
            violations.append("missing_calibration_report_ref")
        if regret_report_ref is None:
            violations.append("missing_regret_report_ref")
    if calibration_report is None:
        violations.append("missing_calibration_report")
    elif not calibration_report.default_enable_allowed:
        violations.extend(f"calibration_blocker:{item}" for item in calibration_report.blockers)
    return sorted(set(violations))


__all__ = [
    "VOICalibrationReport",
    "VOIShadowBaselineComparison",
    "build_voi_calibration_report",
    "compare_voi_to_static_baseline",
    "validate_voi_default_enable",
]
