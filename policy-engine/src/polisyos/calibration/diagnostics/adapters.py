"""Adapters from calibration diagnostics into governance report surfaces."""

from __future__ import annotations

from collections.abc import Mapping  # noqa: TC003 - public annotations are resolved at runtime.
from typing import TYPE_CHECKING, Any

from polisyos.ir.analytics.calibration_diagnostics import (
    CalibrationDiagnosticsReport,  # noqa: TC001 - runtime-resolvable public report annotations.
)
from polisyos.ir.governance.validation import ValidationIssue, ValidationReport

if TYPE_CHECKING:
    from polisyos.ir.analytics.calibration_diagnostics import CalibrationDiagnosticIssue


def to_validation_report(
    *,
    diagnostics: CalibrationDiagnosticsReport,
    thresholds: Mapping[str, Any] | None = None,
    payload_metadata: Mapping[str, Any] | None = None,
) -> ValidationReport:
    """Project a calibration diagnostics report into governance ValidationReport."""

    resolved_thresholds = {
        "ece_max": 0.05,
        "brier_max": 0.20,
        "pvalue_min": 0.05,
        "min_events": 100,
        **dict(thresholds or {}),
    }

    interval_status, interval_comparisons, interval_path = (
        diagnostics._interval_coverage_admission()
    )
    issues: list[ValidationIssue] = []
    issues.extend(_threshold_issues(diagnostics, resolved_thresholds))
    issues.extend(_diagnostic_issues(diagnostics.issues))
    issues.extend(
        _interval_admission_issues(
            diagnostics, interval_status, interval_comparisons, interval_path
        )
    )
    issues.extend(_test_assumption_issues(diagnostics))

    normalized_payload = {
        "calibration": {
            **dict(payload_metadata or {}),
            "task": diagnostics.task,
            "target_type": diagnostics.target_type,
            "primary_curve": diagnostics.primary_curve,
            "n_obs": diagnostics.metrics.n_obs,
            "event_count": diagnostics.metrics.event_count,
            "metrics": diagnostics.metrics.model_dump(exclude_none=True),
            "tests": {
                test.test_id: test.model_dump(exclude_none=True) for test in diagnostics.tests
            },
            "primary_curve_bins": [
                bin_item.model_dump(exclude_none=True)
                for bin_item in diagnostics.curves.get(diagnostics.primary_curve or "", ())
            ],
            "per_class": {
                label: metrics.model_dump(exclude_none=True)
                for label, metrics in diagnostics.per_class.items()
            },
            "per_group": {
                label: metrics.model_dump(exclude_none=True)
                for label, metrics in diagnostics.per_group.items()
            },
            "recommended_action": diagnostics.recommended_action,
            "warnings": list(diagnostics.warnings),
            "interval_coverage": diagnostics.metadata.get("interval_coverage"),
            **(
                {
                    "reconciled_interval_coverage": {
                        "status": interval_status,
                        "n_comparisons": interval_comparisons,
                    },
                    "measurement_source_assurance": "not_established",
                }
                if diagnostics.task == "continuous"
                else {}
            ),
        }
    }

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    summary = (
        f"Calibration diagnostics produced {error_count} error(s) and {warning_count} warning(s)."
    )
    repair_attempt = diagnostics.metadata.get("repair_log") or None

    gate_failures = [issue.code for issue in issues if issue.severity == "error" and issue.code]
    if diagnostics.task == "continuous":
        gate_failures.append("calibration_measurement_source_not_established")
    verdict_fields: dict[str, Any] = {}
    if error_count:
        verdict_fields = {"verdict": "fail", "readiness": "blocked", "gate_failures": gate_failures}
    elif diagnostics.task == "continuous":
        verdict_fields = {
            "verdict": "blocked",
            "readiness": "blocked",
            "gate_failures": gate_failures,
        }

    return ValidationReport(
        error_summary=summary,
        issues=issues,
        repair_attempt=None if repair_attempt is None else str(repair_attempt),
        diff_before_after=diagnostics.metadata.get("diff_before_after"),
        normalized_payload=normalized_payload,
        **verdict_fields,
    )


def _threshold_issues(
    diagnostics: CalibrationDiagnosticsReport,
    thresholds: Mapping[str, Any],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    metrics = diagnostics.metrics

    if metrics.ece is not None and metrics.ece > float(thresholds["ece_max"]):
        issues.append(
            _make_issue(
                path="calibration.metrics.ece",
                code="CALIB_ECE_HIGH",
                severity="warning",
                message="Expected calibration error exceeds the configured maximum.",
                expected=f"<={float(thresholds['ece_max']):.4f}",
                actual=metrics.ece,
            )
        )
    if metrics.brier is not None and metrics.brier > float(thresholds["brier_max"]):
        issues.append(
            _make_issue(
                path="calibration.metrics.brier",
                code="CALIB_BRIER_HIGH",
                severity="warning",
                message="Brier score exceeds the configured maximum.",
                expected=f"<={float(thresholds['brier_max']):.4f}",
                actual=metrics.brier,
            )
        )
    if metrics.event_count is not None and metrics.event_count < int(thresholds["min_events"]):
        issues.append(
            _make_issue(
                path="calibration.data.event_count",
                code="CALIB_TOO_FEW_EVENTS",
                severity="warning",
                message=(
                    "Event count is below the configured minimum for stable calibration review."
                ),
                expected=f">={int(thresholds['min_events'])}",
                actual=metrics.event_count,
            )
        )

    for test in diagnostics.tests:
        if test.p_value is None:
            continue
        if test.p_value >= float(thresholds["pvalue_min"]):
            continue
        code = "CALIB_TEST_REJECTED" if test.test_id == "spiegelhalter" else "CALIB_HL_REJECTED"
        issues.append(
            _make_issue(
                path=f"calibration.tests.{test.test_id}.p_value",
                code=code,
                severity="warning",
                message=f"{test.test_id} rejects the null of acceptable calibration fit.",
                expected=f">={float(thresholds['pvalue_min']):.4f}",
                actual=test.p_value,
            )
        )
    return issues


def _diagnostic_issues(
    issues: tuple[CalibrationDiagnosticIssue, ...],
) -> list[ValidationIssue]:
    return [
        _make_issue(
            path=item.path or "calibration",
            code=item.code,
            severity=item.severity.value,
            message=item.message,
            expected=item.expected,
            actual=item.actual,
        )
        for item in issues
    ]


def _test_assumption_issues(diagnostics: CalibrationDiagnosticsReport) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for test in diagnostics.tests:
        if test.assumptions_ok:
            continue
        issues.append(
            _make_issue(
                path=f"calibration.tests.{test.test_id}",
                code="CALIB_TEST_ASSUMPTIONS_FAILED",
                severity="warning",
                message=(
                    f"{test.test_id} assumptions are not satisfied; "
                    "treat this test as advisory only."
                ),
                expected="assumptions_ok=True",
                actual={"assumptions_ok": test.assumptions_ok, "notes": list(test.notes)},
            )
        )
    return issues


def _interval_admission_issues(
    diagnostics: CalibrationDiagnosticsReport,
    status: str | None,
    comparisons: int | None,
    issue_path: str | None,
) -> list[ValidationIssue]:
    """Fail closed when a continuous report lacks measured interval comparisons."""

    if diagnostics.task != "continuous":
        return []
    existing_codes = {issue.code for issue in diagnostics.issues if issue.severity.value == "error"}
    if status == "evaluated":
        return []
    code = "CALIB_INTERVAL_INCOMPLETE" if status == "incomplete" else "CALIB_INTERVAL_NOT_EVALUATED"
    if code in existing_codes:
        return []
    return [
        _make_issue(
            path=issue_path or "calibration.curves.interval_coverage",
            code=code,
            severity="error",
            message="Continuous calibration lacks a reconciled interval comparison basis.",
            expected=">=1 complete internally consistent interval comparison",
            actual={"status": status, "n_comparisons": comparisons},
        )
    ]


def _make_issue(
    *,
    path: str,
    code: str,
    severity: str,
    message: str,
    expected: object,
    actual: object,
) -> ValidationIssue:
    return ValidationIssue(
        loc=[part for part in path.split(".") if part],
        message=message,
        error_type=code,
        input_value=actual,
        path=path,
        code=code,
        expected=expected,
        actual=actual,
        severity=severity,
    )


__all__ = [
    "to_validation_report",
]
