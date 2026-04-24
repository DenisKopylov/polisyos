"""Tests for calibration diagnostics IR contracts."""

from __future__ import annotations

import pytest

from polisyos.ir.analytics.calibration_diagnostics import (
    CalibrationCurveBin,
    CalibrationDiagnosticIssue,
    CalibrationDiagnosticsReport,
    CalibrationMetrics,
    CalibrationTestResult,
)
from polisyos.ir.analytics.query_validation_report import ValidationSeverity


def test_calibration_diagnostics_report_summary_and_flags() -> None:
    report = CalibrationDiagnosticsReport(
        task="binary",
        target_type="probability",
        metrics=CalibrationMetrics(n_obs=20, event_count=8, brier=0.12, ece=0.03),
        curves={
            "uniform_5": (
                CalibrationCurveBin(
                    lower=0.0, upper=0.2, count=4, mean_predicted=0.1, mean_observed=0.0
                ),
            )
        },
        tests=(
            CalibrationTestResult(
                test_id="spiegelhalter", statistic=0.1, p_value=0.92, passed=True
            ),
        ),
        issues=(
            CalibrationDiagnosticIssue(
                code="CALIB_TOO_FEW_EVENTS",
                message="Need more events for stable slices.",
                severity=ValidationSeverity.WARNING,
                path="calibration.data.event_count",
            ),
        ),
        warnings=("coarse_holdout_only",),
        primary_curve="uniform_5",
    )

    assert report.has_errors() is False
    assert report.has_warnings() is True
    assert "CalibrationDiagnostics[VALID]" in report.to_summary()
    assert "ece=0.0300" in report.to_summary()
    receipt = report.to_truthfulness_receipt()
    assert receipt.runtime_truthfulness_tier == "unverified"
    assert receipt.truthfulness_scope == "predictive_calibration"


def test_calibration_diagnostics_report_is_frozen() -> None:
    report = CalibrationDiagnosticsReport(
        task="binary",
        target_type="probability",
        metrics=CalibrationMetrics(n_obs=1),
    )
    with pytest.raises((TypeError, Exception)):
        report.task = "continuous"


def test_calibration_diagnostics_report_returns_approximate_receipt_when_holdout_is_healthy() -> (
    None
):
    report = CalibrationDiagnosticsReport(
        task="binary",
        target_type="probability",
        metrics=CalibrationMetrics(n_obs=128, event_count=52, brier=0.11, ece=0.02),
    )

    receipt = report.to_truthfulness_receipt()
    assert receipt.runtime_truthfulness_tier == "approximate_calibrated"
    assert receipt.degradation_reasons == ()
