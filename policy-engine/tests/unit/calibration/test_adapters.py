"""Tests for calibration diagnostics adapters."""

from __future__ import annotations

from polisyos.calibration import evaluate_binary, evaluate_multiclass, to_validation_report


def test_to_validation_report_projects_threshold_findings_and_payload() -> None:
    diagnostics = evaluate_binary(
        y_true=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
        y_prob=[0.95, 0.05, 0.90, 0.10, 0.85, 0.15],
        tests=["spiegelhalter"],
    )

    report = to_validation_report(
        diagnostics=diagnostics,
        thresholds={"ece_max": 0.01, "min_events": 10, "pvalue_min": 0.5},
        payload_metadata={"model_id": "policy_v1", "split": "holdout"},
    )

    codes = {issue.code for issue in report.issues}
    assert "CALIB_ECE_HIGH" in codes
    assert "CALIB_TOO_FEW_EVENTS" in codes
    assert report.normalized_payload is not None
    assert report.normalized_payload["calibration"]["model_id"] == "policy_v1"
    assert report.normalized_payload["calibration"]["metrics"]["n_obs"] == 6
    assert report.issues[0].path is not None


def test_to_validation_report_includes_multiclass_summary_sections() -> None:
    diagnostics = evaluate_multiclass(
        y_true=[0, 1, 2, 0, 1, 2],
        y_prob=[
            [0.8, 0.1, 0.1],
            [0.1, 0.8, 0.1],
            [0.1, 0.2, 0.7],
            [0.7, 0.2, 0.1],
            [0.2, 0.7, 0.1],
            [0.2, 0.2, 0.6],
        ],
        curves={"binning": ["quantile"], "n_bins": [3]},
    )

    report = to_validation_report(diagnostics=diagnostics)

    payload = report.normalized_payload["calibration"]
    assert payload["primary_curve_bins"]
    assert set(payload["per_class"]) == {"0", "1", "2"}
