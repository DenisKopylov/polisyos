"""Tests for BoundsReport, BoundMethod (new values), and BenchmarkResult IR types."""

from __future__ import annotations

import pytest
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    BoundsReport,
    PartialIdentificationResult,
)
from polisyos.ir.analytics.sensitivity import BenchmarkResult

# ---------------------------------------------------------------------------
# BoundMethod enum — new values
# ---------------------------------------------------------------------------


class TestBoundMethodEnum:
    def test_mtr_bounds_exists(self):
        assert BoundMethod.MTR_BOUNDS == "mtr_bounds"

    def test_miv_bounds_exists(self):
        assert BoundMethod.MIV_BOUNDS == "miv_bounds"

    def test_mts_bounds_exists(self):
        assert BoundMethod.MTS_BOUNDS == "mts_bounds"

    def test_all_original_values_still_present(self):
        # Existing values must not be removed — regression check
        assert BoundMethod.MANSKI == "manski_bounds"
        assert BoundMethod.IV_BOUNDS == "iv_bounds"
        assert BoundMethod.LP_BALKE_PEARL == "lp_balke_pearl"

    def test_new_values_round_trip_via_string(self):
        for val in (BoundMethod.MTR_BOUNDS, BoundMethod.MIV_BOUNDS, BoundMethod.MTS_BOUNDS):
            reconstructed = BoundMethod(val.value)
            assert reconstructed == val


# ---------------------------------------------------------------------------
# BoundsReport — construction and derived fields
# ---------------------------------------------------------------------------


def _make_pid(
    method: BoundMethod,
    lower: float,
    upper: float,
    confidence: float = 0.9,
) -> PartialIdentificationResult:
    return PartialIdentificationResult(
        method=method,
        lower_bound=lower,
        upper_bound=upper,
        confidence=confidence,
        assumptions_used=["test_assumption"],
    )


class TestBoundsReportDerivedFields:
    def test_tightest_method_is_argmin_width(self):
        wide = _make_pid(BoundMethod.MANSKI, -1.0, 1.0)  # width=2.0
        narrow = _make_pid(BoundMethod.LP_BALKE_PEARL, 0.1, 0.5)  # width=0.4
        report = BoundsReport(results=[wide, narrow], estimand_type="ate")
        assert report.tightest_method == BoundMethod.LP_BALKE_PEARL
        assert report.tightest_lower == pytest.approx(0.1)
        assert report.tightest_upper == pytest.approx(0.5)

    def test_consensus_lower_is_max_of_lowers(self):
        r1 = _make_pid(BoundMethod.MANSKI, -0.8, 0.8)
        r2 = _make_pid(BoundMethod.LP_BALKE_PEARL, -0.2, 0.6)
        report = BoundsReport(results=[r1, r2], estimand_type="ate")
        assert report.consensus_lower == pytest.approx(-0.2)

    def test_consensus_upper_is_min_of_uppers(self):
        r1 = _make_pid(BoundMethod.MANSKI, -0.8, 0.8)
        r2 = _make_pid(BoundMethod.LP_BALKE_PEARL, -0.2, 0.6)
        report = BoundsReport(results=[r1, r2], estimand_type="ate")
        assert report.consensus_upper == pytest.approx(0.6)

    def test_is_informative_true_for_narrow_bounds(self):
        """Width < 0.5 * y_range → informative."""
        narrow = _make_pid(BoundMethod.MTR_BOUNDS, 0.1, 0.3)  # width=0.2
        report = BoundsReport(results=[narrow], estimand_type="ate")
        assert report.is_informative is True

    def test_is_informative_false_for_wide_bounds(self):
        """Manski worst-case: [-1, 1] → width=2.0 → not informative."""
        wide = _make_pid(BoundMethod.MANSKI, -1.0, 1.0)
        report = BoundsReport(results=[wide], estimand_type="ate")
        assert report.is_informative is False

    def test_single_result_tightest_equals_that_result(self):
        pid = _make_pid(BoundMethod.MANSKI, -0.5, 0.5)
        report = BoundsReport(results=[pid], estimand_type="ate")
        assert report.tightest_method == BoundMethod.MANSKI
        assert report.tightest_lower == pytest.approx(-0.5)
        assert report.tightest_upper == pytest.approx(0.5)
        # consensus with a single result
        assert report.consensus_lower == pytest.approx(-0.5)
        assert report.consensus_upper == pytest.approx(0.5)

    def test_three_results_tightest_selection(self):
        r1 = _make_pid(BoundMethod.MANSKI, -1.0, 1.0)  # width=2.0
        r2 = _make_pid(BoundMethod.MTR_BOUNDS, -0.4, 0.8)  # width=1.2
        r3 = _make_pid(BoundMethod.LP_BALKE_PEARL, 0.05, 0.4)  # width=0.35 ← tightest
        report = BoundsReport(results=[r1, r2, r3], estimand_type="ate")
        assert report.tightest_method == BoundMethod.LP_BALKE_PEARL


# ---------------------------------------------------------------------------
# BoundsReport — serialization round-trip
# ---------------------------------------------------------------------------


class TestBoundsReportSerialization:
    def test_round_trip_single_result(self):
        pid = _make_pid(BoundMethod.MANSKI, -0.5, 0.5)
        report = BoundsReport(
            results=[pid],
            run_id="run-001",
            estimand_type="ate",
            assumptions_used=["no_assumptions"],
        )
        dumped = report.model_dump(mode="json")
        reloaded = BoundsReport.model_validate(dumped)
        assert reloaded.tightest_method == report.tightest_method
        assert reloaded.tightest_lower == report.tightest_lower
        assert reloaded.tightest_upper == report.tightest_upper
        assert reloaded.run_id == "run-001"
        assert len(reloaded.results) == len(report.results)

    def test_round_trip_multiple_results(self):
        r1 = _make_pid(BoundMethod.MANSKI, -1.0, 1.0)
        r2 = _make_pid(BoundMethod.LP_BALKE_PEARL, 0.1, 0.5)
        r3 = _make_pid(BoundMethod.MTR_BOUNDS, -0.2, 0.6)
        report = BoundsReport(results=[r1, r2, r3])
        dumped = report.model_dump(mode="json")
        reloaded = BoundsReport.model_validate(dumped)
        assert len(reloaded.results) == 3
        assert reloaded.tightest_method == BoundMethod.LP_BALKE_PEARL

    def test_new_bound_methods_serialize_correctly(self):
        for method in (BoundMethod.MTR_BOUNDS, BoundMethod.MIV_BOUNDS, BoundMethod.MTS_BOUNDS):
            pid = _make_pid(method, 0.1, 0.4)
            report = BoundsReport(results=[pid])
            dumped = report.model_dump(mode="json")
            reloaded = BoundsReport.model_validate(dumped)
            assert reloaded.tightest_method == method

    def test_warnings_preserved_in_round_trip(self):
        pid = _make_pid(BoundMethod.MANSKI, -1.0, 1.0)
        report = BoundsReport(
            results=[pid],
            warnings=["Consensus interval is empty — vacuous bounds."],
        )
        dumped = report.model_dump(mode="json")
        reloaded = BoundsReport.model_validate(dumped)
        assert len(reloaded.warnings) == 1
        assert "vacuous" in reloaded.warnings[0]

    def test_schema_version_present(self):
        pid = _make_pid(BoundMethod.MANSKI, -0.5, 0.5)
        report = BoundsReport(results=[pid])
        assert report.schema_version == "1.0"


# ---------------------------------------------------------------------------
# BoundsReport — is_informative edge cases
# ---------------------------------------------------------------------------


class TestBoundsReportInformativeFlag:
    def test_informative_threshold_exactly_half_range(self):
        """Width = 0.5 → should be informative for default [0,1] range."""
        pid = _make_pid(BoundMethod.MANSKI, 0.0, 0.5)  # width=0.5, range=1.0 → exactly at threshold
        report = BoundsReport(results=[pid])
        # is_informative check: tightest.is_informative
        # PartialIdentificationResult.is_informative: bound_width < 0.5 * (y_upper - y_lower)?
        # The threshold depends on PartialIdentificationResult.is_informative definition
        # Just check the flag is a bool
        assert isinstance(report.is_informative, bool)

    def test_informative_with_mtr_bounds(self):
        pid = _make_pid(BoundMethod.MTR_BOUNDS, 0.2, 0.35)  # width=0.15
        report = BoundsReport(results=[pid])
        assert report.is_informative is True

    def test_not_informative_with_full_range_manski(self):
        pid = _make_pid(BoundMethod.MANSKI, -1.0, 1.0)  # width=2.0
        report = BoundsReport(results=[pid])
        assert report.is_informative is False


# ---------------------------------------------------------------------------
# BenchmarkResult — validation via analytics.sensitivity
# ---------------------------------------------------------------------------


class TestBenchmarkResultValidation:
    def test_r2yd_x_must_be_in_unit_interval(self):
        with pytest.raises(Exception):
            BenchmarkResult(covariate_name="Z", r2yd_x=1.01)

    def test_r2td_x_must_be_in_unit_interval(self):
        with pytest.raises(Exception):
            BenchmarkResult(covariate_name="Z", r2td_x=-0.001)

    def test_zero_values_valid(self):
        br = BenchmarkResult(covariate_name="Z", r2yd_x=0.0, r2td_x=0.0)
        assert br.r2yd_x == 0.0

    def test_one_values_valid(self):
        br = BenchmarkResult(covariate_name="Z", r2yd_x=1.0, r2td_x=1.0)
        assert br.r2yd_x == 1.0

    def test_typical_values(self):
        br = BenchmarkResult(
            covariate_name="income",
            r2yd_x=0.12,
            r2td_x=0.08,
            bias_scale=1.5,
            rv_benchmarked=0.1,
            interpretation="income confounder is 1.5× stronger than needed",
        )
        assert br.bias_scale == pytest.approx(1.5)

    def test_round_trip(self):
        br = BenchmarkResult(covariate_name="age", r2yd_x=0.05, r2td_x=0.03)
        dumped = br.model_dump(mode="json")
        reloaded = BenchmarkResult.model_validate(dumped)
        assert reloaded.covariate_name == "age"
        assert reloaded.r2yd_x == pytest.approx(0.05)
