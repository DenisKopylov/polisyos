"""Typed IR contracts for probabilistic calibration diagnostics."""

from __future__ import annotations

import math
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics._truthfulness import (
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

        interval_status, interval_comparisons, _ = self._interval_coverage_admission()
        if self.truthfulness_receipt is not None and self.task != "continuous":
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
        issue_codes = {issue.code for issue in self.issues}
        if interval_status == "not_evaluated" or "CALIB_INTERVAL_NOT_EVALUATED" in issue_codes:
            runtime_tier = TruthfulnessTier.UNVERIFIED
            degradation_reasons.append("interval_coverage_not_evaluated")
        elif interval_status == "incomplete" or "CALIB_INTERVAL_INCOMPLETE" in issue_codes:
            runtime_tier = TruthfulnessTier.UNVERIFIED
            degradation_reasons.append("interval_coverage_incomplete")
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

        candidate_numeric_tier = runtime_tier
        if self.task == "continuous":
            # A report's consistent summaries do not establish the source of
            # the observations or interval sets. Keep that distinction typed
            # in the receipt instead of granting authority from self-report.
            runtime_tier = TruthfulnessTier.UNVERIFIED
            degradation_reasons.append("measurement_source_not_established")

        diagnostics = {
            "task": self.task,
            "target_type": self.target_type,
            "n_obs": n_obs,
            "brier": self.metrics.brier,
            "ece": ece,
            "mce": self.metrics.mce,
            "warnings": list(self.warnings),
            "issues": sorted(issue_codes),
            "has_errors": self.has_errors(),
            "rejected_tests": list(rejected_tests),
            "recommended_action": self.recommended_action,
            "interval_coverage_status": interval_status,
            "interval_coverage_comparisons": interval_comparisons,
            **(
                {
                    "candidate_numeric_tier": candidate_numeric_tier.value,
                    "measurement_source_assurance": "not_established",
                }
                if self.task == "continuous"
                else {}
            ),
        }
        return TruthfulnessReceipt(
            runtime_truthfulness_tier=runtime_tier,
            truthfulness_scope=TruthfulnessScope.PREDICTIVE_CALIBRATION,
            diagnostics=diagnostics,
            degradation_reasons=tuple(dict.fromkeys(degradation_reasons)),
        )

    def _interval_coverage_admission(self) -> tuple[str | None, int | None, str | None]:
        """Reconcile the recorded comparison basis, without asserting its origin.

        Counts are derived from curve bins; producer metadata is checked only
        for agreement and cannot create an observed comparison. The recorded
        request is itself a declaration and cannot prove source provenance.
        """
        if self.task != "continuous":
            return None, None, None
        bins = self.curves.get("interval_coverage", ())
        comparisons = len(bins)
        coverage = self.metadata.get("interval_coverage")
        if not isinstance(coverage, dict):
            return (
                ("incomplete" if bins else "not_evaluated"),
                comparisons,
                "calibration.curves.interval_coverage",
            )

        requested = coverage.get("requested_levels")
        evaluated = coverage.get("evaluated_levels")
        skipped = coverage.get("skipped_levels")
        nominal = self.metadata.get("nominal_levels")
        if not all(
            isinstance(item, (list, tuple)) for item in (requested, evaluated, skipped, nominal)
        ):
            return (
                ("incomplete" if bins else "not_evaluated"),
                comparisons,
                "calibration.curves.interval_coverage",
            )
        levels = [*requested, *evaluated, *skipped, *nominal]
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0.0 < value < 1.0
            for value in levels
        ):
            return "incomplete", comparisons, "calibration.curves.interval_coverage"
        if not requested and not bins:
            return "not_evaluated", 0, "calibration.curves.interval_coverage"
        if (
            len(requested) != len(set(requested))
            or list(nominal) != list(requested)
            or len(evaluated) != len(set(evaluated))
            or len(skipped) != len(set(skipped))
            or set(evaluated).intersection(skipped)
            or set(requested) != set(evaluated).union(skipped)
            or skipped
            or len(evaluated) != comparisons
            or coverage.get("status") != "evaluated"
            or isinstance(coverage.get("n_comparisons"), bool)
            or not isinstance(coverage.get("n_comparisons"), int)
            or coverage.get("n_comparisons") != comparisons
            or not bins
            or self.metrics.n_obs <= 0
        ):
            return "incomplete", comparisons, "calibration.curves.interval_coverage"

        gaps: list[float] = []
        for level, item in zip(evaluated, bins, strict=True):
            predicted = item.mean_predicted
            observed = item.mean_observed
            if (
                item.count != self.metrics.n_obs
                or predicted is None
                or observed is None
                or not math.isfinite(predicted)
                or not math.isfinite(observed)
                or not math.isclose(
                    observed * item.count,
                    round(observed * item.count),
                    rel_tol=0.0,
                    abs_tol=1e-8,
                )
                or not math.isclose(predicted, level, rel_tol=0.0, abs_tol=1e-12)
                or not math.isclose(item.lower, level, rel_tol=0.0, abs_tol=1e-12)
                or not math.isclose(item.upper, level, rel_tol=0.0, abs_tol=1e-12)
            ):
                return "incomplete", comparisons, "calibration.curves.interval_coverage"
            gap = abs(observed - predicted)
            if item.absolute_gap is not None and not math.isclose(
                item.absolute_gap, gap, rel_tol=1e-9, abs_tol=1e-12
            ):
                return "incomplete", comparisons, "calibration.curves.interval_coverage"
            gaps.append(gap)
        ece = math.fsum(gaps) / comparisons
        if self.metrics.ece is None or not math.isclose(
            self.metrics.ece, ece, rel_tol=1e-9, abs_tol=1e-12
        ):
            return "incomplete", comparisons, "calibration.metrics.ece"
        if self.metrics.mce is not None and not math.isclose(
            self.metrics.mce, max(gaps), rel_tol=1e-9, abs_tol=1e-12
        ):
            return "incomplete", comparisons, "calibration.metrics.mce"
        rmsce = math.sqrt(math.fsum(gap * gap for gap in gaps) / comparisons)
        if self.metrics.rmsce is not None and not math.isclose(
            self.metrics.rmsce, rmsce, rel_tol=1e-9, abs_tol=1e-12
        ):
            return "incomplete", comparisons, "calibration.metrics.rmsce"
        return "evaluated", comparisons, None


__all__ = [
    "CalibrationCurveBin",
    "CalibrationDiagnosticIssue",
    "CalibrationDiagnosticsReport",
    "CalibrationMetricInterval",
    "CalibrationMetrics",
    "CalibrationTestResult",
]
