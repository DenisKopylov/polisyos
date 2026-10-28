"""Source-only adversarial proposal for LA-052 receipt consistency.

This module is a proposal, not an executed test. It uses the existing public
continuous evaluator, report conversions, and typed IR surfaces. The synthetic
95/100 case is only a numeric oracle; it does not establish source origin,
issuer, external calibration, or production provenance.
"""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.calibration import evaluate_continuous, to_validation_report
from polisyos.ir.analytics import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
    extract_truthfulness_receipt,
)
from polisyos.ir.analytics.calibration_diagnostics import (
    CalibrationCurveBin,
    CalibrationDiagnosticsReport,
    CalibrationMetrics,
)


def _continuous_report(
    *,
    n_obs: int = 100,
    ece: float | None = 0.0,
    curve_levels: tuple[float, ...] = (0.95,),
    observed: tuple[float, ...] = (0.95,),
    counts: tuple[int, ...] | None = None,
    requested: tuple[float, ...] | None = None,
    evaluated: tuple[float, ...] | None = None,
    skipped: tuple[float, ...] = (),
    status: str = "evaluated",
    n_comparisons: int | None = None,
    embedded_receipt: TruthfulnessReceipt | None = None,
    reported_gaps: tuple[float, ...] | None = None,
) -> CalibrationDiagnosticsReport:
    """Build an ordinary typed report, including semantically adversarial shapes."""

    resolved_requested = curve_levels if requested is None else requested
    resolved_evaluated = curve_levels if evaluated is None else evaluated
    resolved_counts = counts or tuple(n_obs for _ in curve_levels)
    bins = tuple(
        CalibrationCurveBin(
            lower=level,
            upper=level,
            count=count,
            mean_predicted=level,
            mean_observed=coverage,
            absolute_gap=(abs(coverage - level) if reported_gaps is None else reported_gaps[index]),
        )
        for index, (level, coverage, count) in enumerate(
            zip(curve_levels, observed, resolved_counts, strict=True)
        )
    )
    return CalibrationDiagnosticsReport(
        task="continuous",
        target_type="interval_set",
        metrics=CalibrationMetrics(
            n_obs=n_obs,
            ece=ece,
            mce=ece,
            rmsce=ece,
        ),
        curves={"interval_coverage": bins},
        primary_curve="interval_coverage",
        metadata={
            "nominal_levels": list(resolved_requested),
            "interval_width_mean": {str(level): 0.2 for level in resolved_requested},
            "interval_coverage": {
                "status": status,
                "n_comparisons": (len(curve_levels) if n_comparisons is None else n_comparisons),
                "requested_levels": list(resolved_requested),
                "evaluated_levels": list(resolved_evaluated),
                "skipped_levels": list(skipped),
            },
        },
        truthfulness_receipt=embedded_receipt,
    )


def _positive_embedded_receipt() -> TruthfulnessReceipt:
    """Return a structurally valid positive receipt without bound source evidence."""

    return TruthfulnessReceipt(
        runtime_truthfulness_tier=TruthfulnessTier.APPROXIMATE_CALIBRATED,
        truthfulness_scope=TruthfulnessScope.PREDICTIVE_CALIBRATION,
        diagnostics={"task": "continuous", "ece": 0.0},
    )


def _assert_source_origin_residual(
    diagnostics: CalibrationDiagnosticsReport,
    *,
    candidate_tier: TruthfulnessTier = TruthfulnessTier.APPROXIMATE_CALIBRATED,
) -> None:
    """Keep numeric fit separate from the unestablished measurement source."""

    receipt = diagnostics.to_truthfulness_receipt()
    assert receipt.runtime_truthfulness_tier is TruthfulnessTier.UNVERIFIED
    assert receipt.truthfulness_scope is TruthfulnessScope.PREDICTIVE_CALIBRATION
    assert receipt.diagnostics["candidate_numeric_tier"] == candidate_tier
    assert receipt.diagnostics["measurement_source_assurance"] == "not_established"

    validation = to_validation_report(diagnostics=diagnostics)
    assert validation.verdict == "blocked"
    assert validation.readiness == "blocked"


def _assert_measurement_failure(
    diagnostics: CalibrationDiagnosticsReport,
    *,
    issue_path: str = "calibration.curves.interval_coverage",
) -> None:
    """Require fail-closed consumer status for missing or contradictory measurement."""

    assert (
        diagnostics.to_truthfulness_receipt().runtime_truthfulness_tier
        is TruthfulnessTier.UNVERIFIED
    )
    validation = to_validation_report(diagnostics=diagnostics)
    assert validation.verdict == "fail"
    assert validation.readiness == "blocked"
    assert any(
        issue.path == issue_path and issue.severity == "error" for issue in validation.issues
    )
    receipt = diagnostics.to_truthfulness_receipt()
    assert receipt.diagnostics["measurement_source_assurance"] == "not_established"


def test_positive_metadata_cannot_admit_an_empty_interval_curve() -> None:
    diagnostics = _continuous_report(
        curve_levels=(),
        observed=(),
        counts=(),
        requested=(0.95,),
        evaluated=(0.95,),
        status="evaluated",
        n_comparisons=1,
        ece=0.0,
    )

    _assert_measurement_failure(diagnostics)


@pytest.mark.parametrize(
    "diagnostics",
    [
        _continuous_report(
            requested=(0.90, 0.95),
            evaluated=(0.95,),
            skipped=(),
            status="evaluated",
        ),
        _continuous_report(n_comparisons=2),
        _continuous_report(evaluated=(0.90,)),
        _continuous_report(skipped=(0.90,), status="evaluated"),
        _continuous_report(
            curve_levels=(0.90, 0.95),
            observed=(0.90, 0.95),
            requested=(0.95,),
            evaluated=(0.95,),
            n_comparisons=2,
        ),
        _continuous_report(counts=(99,)),
    ],
    ids=(
        "requested-evaluated-skipped-partition",
        "comparison-count-vs-bin-count",
        "evaluated-level-vs-bin-level",
        "evaluated-with-skipped-level",
        "unrequested-extra-bin",
        "bin-count-vs-n-obs",
    ),
)
def test_interval_inventory_and_count_mismatches_are_not_admitted(
    diagnostics: CalibrationDiagnosticsReport,
) -> None:
    _assert_measurement_failure(diagnostics)


@pytest.mark.parametrize(
    "diagnostics",
    [
        _continuous_report(
            curve_levels=(0.95, 0.95),
            observed=(0.95, 0.95),
            requested=(0.95, 0.95),
            evaluated=(0.95, 0.95),
            n_comparisons=2,
        ),
        _continuous_report(
            curve_levels=(0.0,),
            observed=(0.0,),
            requested=(0.0,),
            evaluated=(0.0,),
        ),
        _continuous_report(
            curve_levels=(1.0,),
            observed=(1.0,),
            requested=(1.0,),
            evaluated=(1.0,),
        ),
    ],
    ids=("duplicate-level", "zero-level", "one-level"),
)
def test_duplicate_or_out_of_domain_levels_are_not_admitted(
    diagnostics: CalibrationDiagnosticsReport,
) -> None:
    _assert_measurement_failure(diagnostics)


def test_continuous_producer_rejects_duplicate_requested_levels() -> None:
    y_true = np.arange(100, dtype=float).tolist()
    intervals = [[(value - 0.1, value + 0.1) for value in y_true] for _ in range(2)]

    with pytest.raises(ValueError, match="levels"):
        evaluate_continuous(y_true=y_true, intervals=intervals, levels=[0.95, 0.95])


@pytest.mark.parametrize(
    ("ece", "coverage", "expected_gap"),
    [(0.95, 0.95, 0.0), (0.0, 0.0, 0.95)],
    ids=("high-ece-with-zero-gap", "zero-ece-with-zero-coverage"),
)
def test_ece_must_reconcile_with_the_reported_coverage_curve(
    ece: float,
    coverage: float,
    expected_gap: float,
) -> None:
    diagnostics = _continuous_report(ece=ece, observed=(coverage,))
    assert diagnostics.curves["interval_coverage"][0].absolute_gap == pytest.approx(expected_gap)

    _assert_measurement_failure(diagnostics, issue_path="calibration.metrics.ece")


def test_measured_zero_coverage_is_negative_not_a_zero_error_positive() -> None:
    y_true = np.arange(100, dtype=float).tolist()
    diagnostics = evaluate_continuous(
        y_true=y_true,
        intervals={0.95: [(-1000.0, -999.0)] * 100},
    )

    assert diagnostics.metrics.n_obs == 100
    assert diagnostics.metrics.ece == pytest.approx(0.95)
    assert diagnostics.curves["interval_coverage"][0].mean_observed == 0.0
    _assert_source_origin_residual(
        diagnostics,
        candidate_tier=TruthfulnessTier.UNVERIFIED,
    )
    validation = to_validation_report(diagnostics=diagnostics)
    assert any(issue.code == "CALIB_ECE_HIGH" for issue in validation.issues)


def test_generated_95_of_100_is_a_numeric_positive_but_receipt_stays_limited() -> None:
    y_true = np.arange(100, dtype=float).tolist()
    intervals = [(value - 0.1, value + 0.1) for value in y_true[:95]] + [(-1000.0, -999.0)] * 5
    diagnostics = evaluate_continuous(
        y_true=y_true,
        intervals={0.95: intervals},
    )

    assert diagnostics.metrics.n_obs == 100
    assert diagnostics.metrics.ece == pytest.approx(0.0)
    assert diagnostics.curves["interval_coverage"][0].count == 100
    assert diagnostics.curves["interval_coverage"][0].mean_observed == pytest.approx(0.95)
    _assert_source_origin_residual(diagnostics)


def test_partial_measured_input_is_limited_even_when_its_ece_is_zero() -> None:
    y_true = np.arange(100, dtype=float).tolist()
    valid = [(value - 0.1, value + 0.1) for value in y_true[:95]] + [(-1000.0, -999.0)] * 5
    diagnostics = evaluate_continuous(
        y_true=y_true,
        intervals=[[], valid],
        levels=[0.90, 0.95],
    )

    coverage = diagnostics.metadata["interval_coverage"]
    assert coverage["status"] == "incomplete"
    assert coverage["requested_levels"] == [0.90, 0.95]
    assert coverage["evaluated_levels"] == [0.95]
    assert coverage["skipped_levels"] == [0.90]
    assert diagnostics.metrics.ece == pytest.approx(0.0)
    assert (
        diagnostics.to_truthfulness_receipt().diagnostics["candidate_numeric_tier"]
        == TruthfulnessTier.UNVERIFIED
    )
    _assert_measurement_failure(diagnostics)


def test_hand_authored_coherent_report_without_source_binding_is_limited() -> None:
    diagnostics = _continuous_report()

    _assert_source_origin_residual(diagnostics)


def test_embedded_positive_receipt_cannot_bypass_continuous_recomputation() -> None:
    embedded = _positive_embedded_receipt()
    diagnostics = _continuous_report(
        curve_levels=(),
        observed=(),
        counts=(),
        requested=(0.95,),
        evaluated=(),
        skipped=(0.95,),
        status="not_evaluated",
        n_comparisons=0,
        ece=None,
        embedded_receipt=embedded,
    )

    recomputed = diagnostics.to_truthfulness_receipt()
    extracted = extract_truthfulness_receipt(diagnostics)
    assert recomputed.runtime_truthfulness_tier is TruthfulnessTier.UNVERIFIED
    assert extracted == recomputed
    assert extracted != embedded
    _assert_measurement_failure(diagnostics)


def test_mapping_receipt_extraction_is_not_a_continuous_report_admission() -> None:
    embedded = _positive_embedded_receipt()
    extracted = extract_truthfulness_receipt(
        {"task": "continuous", "truthfulness_receipt": embedded.model_dump(mode="json")}
    )

    # This is the generic mapping extractor's parse boundary only. The Mapping
    # has no typed curve, evaluated denominator, or owner binding to reconcile.
    assert extracted == embedded
    assert extracted is not None
    assert extracted.evidence_ref is None


def test_noncontinuous_report_keeps_its_existing_embedded_receipt_behavior() -> None:
    embedded = TruthfulnessReceipt(
        runtime_truthfulness_tier=TruthfulnessTier.APPROXIMATE_CALIBRATED,
        truthfulness_scope=TruthfulnessScope.PREDICTIVE_CALIBRATION,
    )
    diagnostics = CalibrationDiagnosticsReport(
        task="binary",
        target_type="probability",
        metrics=CalibrationMetrics(n_obs=128, ece=0.02),
        truthfulness_receipt=embedded,
    )

    assert diagnostics.to_truthfulness_receipt() == embedded
    assert extract_truthfulness_receipt(diagnostics) == embedded
    validation = to_validation_report(diagnostics=diagnostics)
    assert validation.verdict == "pass"
    assert validation.readiness == "ready"
    assert all(issue.code != "CALIB_INTERVAL_NOT_EVALUATED" for issue in validation.issues)


@pytest.mark.parametrize(
    ("task", "target_type"), [("binary", "probability"), ("multiclass", "probability")]
)
def test_any_fatal_diagnostic_issue_cannot_leave_a_pass_ready_validation(task, target_type):
    from polisyos.ir.analytics.calibration_diagnostics import CalibrationDiagnosticIssue
    from polisyos.ir.analytics.query_validation_report import ValidationSeverity

    diagnostics = CalibrationDiagnosticsReport(
        task=task,
        target_type=target_type,
        metrics=CalibrationMetrics(n_obs=100, ece=0.0),
        issues=(
            CalibrationDiagnosticIssue(
                code="SOURCE_FATAL", message="fatal", severity=ValidationSeverity.ERROR
            ),
        ),
    )
    report = to_validation_report(diagnostics=diagnostics)
    assert report.verdict == "fail"
    assert report.readiness == "blocked"
    assert any(
        issue.code == "SOURCE_FATAL" and issue.severity == "error" for issue in report.issues
    )


def test_warning_with_the_expected_issue_code_cannot_mask_recomputed_error():
    from polisyos.ir.analytics.calibration_diagnostics import CalibrationDiagnosticIssue
    from polisyos.ir.analytics.query_validation_report import ValidationSeverity

    diagnostics = _continuous_report(
        curve_levels=(),
        observed=(),
        requested=(0.95,),
        evaluated=(),
        skipped=(0.95,),
        status="not_evaluated",
        n_comparisons=0,
        ece=None,
    ).model_copy(
        update={
            "issues": (
                CalibrationDiagnosticIssue(
                    code="CALIB_INTERVAL_INCOMPLETE",
                    message="nonfatal marker",
                    severity=ValidationSeverity.WARNING,
                    path="calibration.curves.interval_coverage",
                ),
            )
        }
    )
    _assert_measurement_failure(diagnostics)


def test_typed_incomplete_report_dominates_a_positive_sidecar_in_real_dispatch_merge():
    from polisyos.core.observability import DeterminismTier
    from polisyos.foundry.methods.backends.dispatch import _merge_dispatch_result
    from polisyos.foundry.methods.backends.protocol import (
        MethodResult,
        MethodTiming,
        ReproducibilityInfo,
    )
    from polisyos.foundry.methods.base import ComputeBackend

    report = _continuous_report(
        curve_levels=(),
        observed=(),
        requested=(0.95,),
        evaluated=(),
        skipped=(0.95,),
        status="not_evaluated",
        n_comparisons=0,
        ece=None,
    )
    positive = _positive_embedded_receipt().model_dump(mode="json")
    assert extract_truthfulness_receipt({"truthfulness_receipt": positive, "report": report}) == (
        report.to_truthfulness_receipt()
    )
    for original_sidecar, overlay_sidecar in (
        ({"truthfulness_receipt": positive}, {}),
        ({}, {"truthfulness_receipt": positive}),
        ({"truthfulness_receipt": positive}, {"truthfulness_receipt": positive}),
    ):
        result = MethodResult(
            output={"report": report},
            artifacts=original_sidecar,
            timing=MethodTiming(wall_time_ms=1.0),
            reproducibility=ReproducibilityInfo(
                backend=ComputeBackend.NUMPY,
                determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
            ),
        )
        merged = _merge_dispatch_result(result=result, artifacts=overlay_sidecar)
        receipt = extract_truthfulness_receipt(merged.artifacts)
        assert receipt is not None
        assert receipt.runtime_truthfulness_tier is TruthfulnessTier.UNVERIFIED
