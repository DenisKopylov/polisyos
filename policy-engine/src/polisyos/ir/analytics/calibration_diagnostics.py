"""Typed IR contracts for probabilistic calibration diagnostics."""
from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
)
from polisyos.ir.analytics.query_validation_report import ValidationSeverity


class CalibrationDiagnosticIssue(BaseModel):
    """One structured finding emitted by calibration diagnostics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: ValidationSeverity
    path: str = ""
    expected: Any | None = None
    actual: Any | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class CalibrationCurveBin(BaseModel):
    """One reliability-bin summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lower: float = Field(ge=0.0, le=1.0)
    upper: float = Field(ge=0.0, le=1.0)
    count: int = Field(ge=0)
    mean_predicted: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_observed: float | None = Field(default=None, ge=0.0, le=1.0)
    absolute_gap: float | None = Field(default=None, ge=0.0)
    ci_low: float | None = Field(default=None, ge=0.0, le=1.0)
    ci_high: float | None = Field(default=None, ge=0.0, le=1.0)


class CalibrationMetricInterval(BaseModel):
    """Confidence interval for one scalar calibration metric."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    low: float
    high: float


class CalibrationTestResult(BaseModel):
    """Statistical test output for calibration fit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    test_id: str = Field(min_length=1)
    statistic: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    df: int | None = Field(default=None, ge=0)
    passed: bool | None = None
    assumptions_ok: bool = True
    notes: tuple[str, ...] = ()


class CalibrationMetrics(BaseModel):
    """Scalar calibration metrics for one prediction surface."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    n_obs: int = Field(ge=0)
    event_count: int | None = Field(default=None, ge=0)
    prevalence: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_predicted_score: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_observed_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    brier: float | None = Field(default=None, ge=0.0)
    log_loss: float | None = Field(default=None, ge=0.0)
    ece: float | None = Field(default=None, ge=0.0)
    mce: float | None = Field(default=None, ge=0.0)
    rmsce: float | None = Field(default=None, ge=0.0)
    ace: float | None = Field(default=None, ge=0.0)
    ence: float | None = Field(default=None, ge=0.0)
    rel: float | None = Field(default=None, ge=0.0)
    res: float | None = Field(default=None, ge=0.0)
    unc: float | None = Field(default=None, ge=0.0)
    intervals: dict[str, CalibrationMetricInterval] = Field(default_factory=dict)


class CalibrationDiagnosticsReport(BaseModel):
    """Top-level typed report for calibration diagnostics."""

    contract_id: ClassVar[str] = "ir.calibration_diagnostics_report.v1"
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    task: Literal["binary", "multiclass", "continuous"]
    target_type: Literal["probability", "logit", "predictive_distribution", "interval_set"]
    metrics: CalibrationMetrics
    curves: dict[str, tuple[CalibrationCurveBin, ...]] = Field(default_factory=dict)
    tests: tuple[CalibrationTestResult, ...] = ()
    issues: tuple[CalibrationDiagnosticIssue, ...] = ()
    warnings: tuple[str, ...] = ()
    primary_curve: str | None = None
    per_class: dict[str, CalibrationMetrics] = Field(default_factory=dict)
    per_group: dict[str, CalibrationMetrics] = Field(default_factory=dict)
    recommended_action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    truthfulness_receipt: TruthfulnessReceipt | None = None

    def has_errors(self) -> bool:
        """Return True if any structured issue is fatal."""

        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    def has_warnings(self) -> bool:
        """Return True when warnings or warning-severity findings exist."""

        return bool(self.warnings) or any(
            issue.severity == ValidationSeverity.WARNING for issue in self.issues
        )

    def to_summary(self) -> str:
        """Return a compact operator-facing summary."""

        status = "INVALID" if self.has_errors() else "VALID"
        parts = [f"CalibrationDiagnostics[{status}]"]
        parts.append(f"task={self.task}")
        parts.append(f"n_obs={self.metrics.n_obs}")
        if self.metrics.ece is not None:
            parts.append(f"ece={self.metrics.ece:.4f}")
        if self.metrics.brier is not None:
            parts.append(f"brier={self.metrics.brier:.4f}")
        if self.tests:
            rejected = [test.test_id for test in self.tests if test.passed is False]
            if rejected:
                parts.append("tests_rejected=" + ",".join(rejected))
        if self.has_warnings():
            parts.append(f"warnings={len(self.warnings)}")
        return " | ".join(parts)

    def to_truthfulness_receipt(self) -> TruthfulnessReceipt:
        """Project calibration diagnostics into the shared truthfulness receipt contract."""

        if self.truthfulness_receipt is not None:
            return self.truthfulness_receipt

        rejected_tests = tuple(
            test.test_id for test in self.tests if test.passed is False or not test.assumptions_ok
        )
        degradation_reasons: list[str] = []
        runtime_tier = TruthfulnessTier.APPROXIMATE_CALIBRATED
        n_obs = int(self.metrics.n_obs)
        ece = self.metrics.ece

        if self.has_errors():
            runtime_tier = TruthfulnessTier.UNVERIFIED
            degradation_reasons.append("fatal_calibration_issue")
        if n_obs < 30:
            runtime_tier = TruthfulnessTier.UNVERIFIED
            degradation_reasons.append("insufficient_holdout_sample")
        if ece is None:
            runtime_tier = TruthfulnessTier.UNVERIFIED
            degradation_reasons.append("missing_ece_metric")
        elif ece > 0.10:
            runtime_tier = TruthfulnessTier.UNVERIFIED
            degradation_reasons.append("ece_above_fail_threshold")
        elif ece > 0.05:
            degradation_reasons.append("ece_above_target_threshold")
        if rejected_tests:
            runtime_tier = TruthfulnessTier.UNVERIFIED
            degradation_reasons.append("calibration_test_rejected")

        diagnostics = {
            "task": self.task,
            "target_type": self.target_type,
            "n_obs": n_obs,
            "brier": self.metrics.brier,
            "ece": ece,
            "mce": self.metrics.mce,
            "warnings": list(self.warnings),
            "has_errors": self.has_errors(),
            "rejected_tests": list(rejected_tests),
            "recommended_action": self.recommended_action,
        }
        return TruthfulnessReceipt(
            runtime_truthfulness_tier=runtime_tier,
            truthfulness_scope=TruthfulnessScope.PREDICTIVE_CALIBRATION,
            diagnostics=diagnostics,
            degradation_reasons=tuple(dict.fromkeys(degradation_reasons)),
        )


__all__ = [
    "CalibrationCurveBin",
    "CalibrationDiagnosticIssue",
    "CalibrationDiagnosticsReport",
    "CalibrationMetricInterval",
    "CalibrationMetrics",
    "CalibrationTestResult",
]
