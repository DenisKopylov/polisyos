"""Tests for Cinelli-Hazlett benchmarking in SensitivityMetrics + SensitivityReport."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData
from polisyos.ir.analytics.sensitivity import BenchmarkResult, SensitivityResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gcd(n: int = 400, *, seed: int = 42) -> GraphCausalData:
    """Simple linear DGP with one observed confounder Z."""
    rng = np.random.default_rng(seed)
    Z = rng.normal(size=n)
    T = (0.6 * Z + rng.normal(0, 0.5, size=n) > 0).astype(float)
    Y = 0.5 * T + 0.4 * Z + rng.normal(0, 0.3, size=n)
    data = np.column_stack([T, Y, Z])
    return GraphCausalData(
        data=data,
        column_names=["T", "Y", "Z"],
        treatment="T",
        outcome="Y",
        graph_dot="digraph { Z -> T; Z -> Y; T -> Y; }",
        graph_ref="cas:graph:test",
        covariates=["Z"],
    )


def _run(gcd: GraphCausalData, params: dict) -> dict:
    from polisyos.foundry.methods.catalog.causal.sensitivity_metrics import SensitivityMetrics

    return SensitivityMetrics.pure_step(gcd, params)


_BASE_PARAMS = {
    "point_estimate": 0.5,
    "confidence_interval": [0.2, 0.8],
    "standard_error": 0.08,
    "sample_size": 400,
    "conversion_method": "ate_to_rr_log",
    "covariates": ["Z"],
}


# ---------------------------------------------------------------------------
# BenchmarkResult IR model validation
# ---------------------------------------------------------------------------


class TestBenchmarkResultModel:
    def test_valid_construction(self):
        br = BenchmarkResult(
            covariate_name="Z",
            r2yd_x=0.15,
            r2td_x=0.20,
            bias_scale=1.5,
        )
        assert br.covariate_name == "Z"
        assert br.r2yd_x == pytest.approx(0.15)
        assert br.r2td_x == pytest.approx(0.20)

    def test_r2yd_x_must_be_in_unit_interval(self):
        with pytest.raises(Exception):
            BenchmarkResult(covariate_name="Z", r2yd_x=1.5)

    def test_r2td_x_must_be_in_unit_interval(self):
        with pytest.raises(Exception):
            BenchmarkResult(covariate_name="Z", r2td_x=-0.01)

    def test_r2_at_zero_is_valid(self):
        br = BenchmarkResult(covariate_name="Z", r2yd_x=0.0, r2td_x=0.0)
        assert br.r2yd_x == 0.0

    def test_r2_at_one_is_valid(self):
        br = BenchmarkResult(covariate_name="Z", r2yd_x=1.0, r2td_x=1.0)
        assert br.r2yd_x == 1.0

    def test_none_r2_fields_are_fine(self):
        br = BenchmarkResult(covariate_name="Z")
        assert br.r2yd_x is None
        assert br.r2td_x is None

    def test_round_trip(self):
        br = BenchmarkResult(
            covariate_name="income",
            r2yd_x=0.12,
            r2td_x=0.08,
            bias_scale=2.0,
            interpretation="robust relative to income",
        )
        dumped = br.model_dump(mode="json")
        reloaded = BenchmarkResult.model_validate(dumped)
        assert reloaded.covariate_name == br.covariate_name
        assert reloaded.r2yd_x == br.r2yd_x
        assert reloaded.bias_scale == br.bias_scale


# ---------------------------------------------------------------------------
# SensitivityMetrics — benchmark_covariates parameter
# ---------------------------------------------------------------------------


class TestSensitivityMetricsBenchmarks:
    def test_benchmarks_skipped_when_not_requested(self):
        gcd = _make_gcd()
        result = _run(gcd, _BASE_PARAMS)
        sr = result["sensitivity_result"]
        assert sr.benchmark_results == []
        assert sr.benchmark_covariates == []

    def test_benchmarks_computed_when_requested(self):
        gcd = _make_gcd(seed=1)
        params = {**_BASE_PARAMS, "benchmark_covariates": ["Z"]}
        result = _run(gcd, params)
        sr = result["sensitivity_result"]
        assert len(sr.benchmark_results) >= 1
        assert "Z" in sr.benchmark_covariates

    def test_benchmark_r2_values_in_unit_interval(self):
        gcd = _make_gcd(seed=2)
        params = {**_BASE_PARAMS, "benchmark_covariates": ["Z"]}
        result = _run(gcd, params)
        sr = result["sensitivity_result"]
        for br in sr.benchmark_results:
            if br.r2yd_x is not None:
                assert 0.0 <= br.r2yd_x <= 1.0, f"r2yd_x={br.r2yd_x} out of [0,1]"
            if br.r2td_x is not None:
                assert 0.0 <= br.r2td_x <= 1.0, f"r2td_x={br.r2td_x} out of [0,1]"

    def test_unknown_covariate_skipped_gracefully(self):
        """Requesting a covariate not in column_names should not crash."""
        gcd = _make_gcd()
        # "W" is not in column_names — should skip gracefully
        params = {**_BASE_PARAMS, "benchmark_covariates": ["W"]}
        result = _run(gcd, params)
        sr = result["sensitivity_result"]
        assert isinstance(sr.benchmark_results, list)

    def test_benchmarks_graceful_without_sensemakr(self, monkeypatch):
        """If sensemakr is unavailable, numpy fallback path should not crash."""
        from polisyos.foundry.methods.catalog.causal import sensitivity_metrics as sm_mod

        monkeypatch.setattr(sm_mod, "_load_sensemakr_module", lambda: None)

        gcd = _make_gcd(seed=4)
        params = {**_BASE_PARAMS, "benchmark_covariates": ["Z"]}
        result = sm_mod.SensitivityMetrics.pure_step(gcd, params)
        sr = result["sensitivity_result"]
        assert isinstance(sr.benchmark_results, list)

    def test_benchmark_result_in_sensitivity_result_is_typed(self):
        """benchmark_results should contain BenchmarkResult objects (or validate as such)."""
        gcd = _make_gcd(seed=5)
        params = {**_BASE_PARAMS, "benchmark_covariates": ["Z"]}
        result = _run(gcd, params)
        sr = result["sensitivity_result"]
        for br in sr.benchmark_results:
            assert isinstance(br, BenchmarkResult)


# ---------------------------------------------------------------------------
# SensitivityReport — overall_robustness_assessment logic
# ---------------------------------------------------------------------------


class TestSensitivityReportAssessment:
    def _make_sensitivity_result(
        self,
        *,
        is_robust: bool,
        e_value: float | None = None,
        rosenbaum_gamma: float | None = None,
        robustness_value: float | None = None,
    ) -> SensitivityResult:
        return SensitivityResult(
            schema_version="1.0",
            is_robust=is_robust,
            e_value=e_value,
            e_value_ci_lower=e_value,
            robustness_value=robustness_value,
            rosenbaum_gamma=rosenbaum_gamma,
        )

    def test_robust_when_is_robust_true_no_breaches(self):
        from polisyos.ir.analytics.sensitivity_report import SensitivityReport

        sr = self._make_sensitivity_result(is_robust=True, e_value=3.0)
        report = SensitivityReport(sensitivity_result=sr)
        assert report.overall_robustness_assessment == "robust"

    def test_fragile_when_is_robust_false_with_breaches(self):
        from polisyos.ir.analytics.sensitivity_report import SensitivityReport

        sr = self._make_sensitivity_result(is_robust=False, e_value=1.1)
        report = SensitivityReport(
            sensitivity_result=sr,
            threshold_breaches={"e_value": 1.1},
        )
        assert report.overall_robustness_assessment == "fragile"

    def test_marginal_when_is_robust_false_no_breaches(self):
        from polisyos.ir.analytics.sensitivity_report import SensitivityReport

        sr = self._make_sensitivity_result(is_robust=False, e_value=1.8)
        report = SensitivityReport(sensitivity_result=sr)
        assert report.overall_robustness_assessment == "marginal"

    def test_recommendations_populated_for_low_evalue(self):
        from polisyos.ir.analytics.sensitivity_report import SensitivityReport

        sr = self._make_sensitivity_result(is_robust=False, e_value=1.1)
        report = SensitivityReport(
            sensitivity_result=sr,
            threshold_breaches={"e_value": 1.1},
        )
        assert len(report.actionable_recommendations) >= 1
        assert any("E-value" in r for r in report.actionable_recommendations)

    def test_recommendations_populated_for_low_rosenbaum(self):
        from polisyos.ir.analytics.sensitivity_report import SensitivityReport

        sr = self._make_sensitivity_result(is_robust=False, rosenbaum_gamma=1.1)
        report = SensitivityReport(
            sensitivity_result=sr,
            threshold_breaches={"rosenbaum_gamma": 1.1},
        )
        assert any("gamma" in r.lower() for r in report.actionable_recommendations)

    def test_recommendations_empty_when_all_robust(self):
        from polisyos.ir.analytics.sensitivity_report import SensitivityReport

        sr = self._make_sensitivity_result(
            is_robust=True, e_value=5.0, rosenbaum_gamma=2.5, robustness_value=0.3
        )
        report = SensitivityReport(sensitivity_result=sr)
        assert report.actionable_recommendations == []

    def test_round_trip_serialization(self):
        from polisyos.ir.analytics.sensitivity_report import SensitivityReport

        sr = self._make_sensitivity_result(is_robust=True, e_value=2.5)
        report = SensitivityReport(
            sensitivity_result=sr,
            run_id="test-run-001",
            estimand_type="ate",
        )
        dumped = report.model_dump(mode="json")
        reloaded = SensitivityReport.model_validate(dumped)
        assert reloaded.overall_robustness_assessment == report.overall_robustness_assessment
        assert reloaded.run_id == "test-run-001"

    def test_with_bounds_report_uninformative_adds_recommendation(self):
        from polisyos.ir.analytics.partial_identification import (
            BoundMethod,
            BoundsReport,
            PartialIdentificationResult,
        )
        from polisyos.ir.analytics.sensitivity_report import SensitivityReport

        pid = PartialIdentificationResult(
            method=BoundMethod.MANSKI,
            lower_bound=-0.9,
            upper_bound=0.9,
            confidence=0.9,
            assumptions_used=["no_assumptions_on_selection"],
        )
        bounds = BoundsReport(results=[pid], estimand_type="ate")
        assert not bounds.is_informative  # width=1.8 >> 0.5

        sr = self._make_sensitivity_result(is_robust=True, e_value=3.0)
        report = SensitivityReport(sensitivity_result=sr, bounds_report=bounds)
        assert any("bounds" in r.lower() for r in report.actionable_recommendations)


# ---------------------------------------------------------------------------
# Phase 7: Advanced Partial Identification Tests
# ---------------------------------------------------------------------------


class TestGeneralBalkePearlBoundsEstimator:
    """Tests for multi-valued Balke-Pearl LP bounds (Phase 7)."""

    def _make_ternary_state(self, n: int = 300, seed: int = 42) -> dict:
        """Ternary treatment (0,1,2), ternary outcome (0,1,2), binary IV."""
        rng = np.random.default_rng(seed)
        Z = rng.integers(0, 2, size=n).astype(float)
        T = np.clip(np.round(rng.uniform(0, 2, size=n) + 0.4 * Z).astype(int), 0, 2).astype(float)
        Y = np.clip(np.round(0.5 * T + rng.normal(0, 0.5, size=n)).astype(int), 0, 2).astype(float)
        return {"outcome": Y, "treatment": T, "instrument": Z}

    def test_ternary_runs_without_error(self):
        from polisyos.foundry.methods.catalog.causal.bounds import (
            GeneralBalkePearlBoundsEstimator,
        )

        state = self._make_ternary_state()
        result = GeneralBalkePearlBoundsEstimator.pure_step(state, {})
        inner = result["result"]
        assert "ate_lower_bound" in inner
        assert "ate_upper_bound" in inner
        assert inner["ate_lower_bound"] <= inner["ate_upper_bound"]

    def test_solver_status_optimal_on_clean_data(self):
        from polisyos.foundry.methods.catalog.causal.bounds import (
            GeneralBalkePearlBoundsEstimator,
        )

        state = self._make_ternary_state()
        result = GeneralBalkePearlBoundsEstimator.pure_step(state, {})
        assert result["result"]["solver_status"] == "optimal"

    def test_binary_case_matches_balke_pearl(self):
        """At K=J=1, GeneralBalkePearl must agree with BalkePearlBoundsEstimator."""
        from polisyos.foundry.methods.catalog.causal.bounds import (
            BalkePearlBoundsEstimator,
            GeneralBalkePearlBoundsEstimator,
        )

        rng = np.random.default_rng(7)
        n = 400
        Z = rng.integers(0, 2, size=n).astype(float)
        T = (rng.random(n) < 0.3 + 0.4 * Z).astype(float)
        Y = (rng.random(n) < 0.2 + 0.35 * T).astype(float)
        state = {"outcome": Y, "treatment": T, "instrument": Z}

        bp = BalkePearlBoundsEstimator.pure_step(state, {})["result"]
        gbp = GeneralBalkePearlBoundsEstimator.pure_step(state, {})["result"]
        assert abs(bp["ate_lower_bound"] - gbp["ate_lower_bound"]) < 0.02
        assert abs(bp["ate_upper_bound"] - gbp["ate_upper_bound"]) < 0.02

    def test_partial_id_result_method_is_general_lp(self):
        from polisyos.foundry.methods.catalog.causal.bounds import (
            GeneralBalkePearlBoundsEstimator,
        )
        from polisyos.ir.analytics.partial_identification import (
            BoundMethod,
            PartialIdentificationResult,
        )

        state = self._make_ternary_state()
        result = GeneralBalkePearlBoundsEstimator.pure_step(state, {})
        pid = PartialIdentificationResult.model_validate(result["result"]["partial_id_result"])
        assert pid.method == BoundMethod.GENERAL_LP_BOUNDS

    def test_bounds_within_outcome_range(self):
        """Bounds must lie within [-max_y_diff, +max_y_diff]."""
        from polisyos.foundry.methods.catalog.causal.bounds import (
            GeneralBalkePearlBoundsEstimator,
        )

        state = self._make_ternary_state()  # Y ∈ {0, 1, 2}
        result = GeneralBalkePearlBoundsEstimator.pure_step(state, {})
        inner = result["result"]
        assert inner["ate_lower_bound"] >= -2.5
        assert inner["ate_upper_bound"] <= 2.5


class TestCopulaBoundsEstimator:
    """Tests for Fan-Park (2010) copula bounds (Phase 7)."""

    def _make_state(self, n: int = 300, seed: int = 1) -> dict:
        rng = np.random.default_rng(seed)
        T = rng.integers(0, 2, size=n).astype(float)
        Y = 0.4 * T + rng.normal(0, 0.2, size=n)
        return {"outcome": Y, "treatment": T}

    def test_runs_without_error(self):
        from polisyos.foundry.methods.catalog.causal.bounds import CopulaBoundsEstimator

        state = self._make_state()
        result = CopulaBoundsEstimator.pure_step(state, {})
        assert "result" in result
        assert "ate_lower_bound" in result["result"]

    def test_bounds_are_ordered(self):
        from polisyos.foundry.methods.catalog.causal.bounds import CopulaBoundsEstimator

        state = self._make_state()
        result = CopulaBoundsEstimator.pure_step(state, {})
        inner = result["result"]
        assert inner["ate_lower_bound"] <= inner["ate_upper_bound"]
        assert inner["quantile_effect_lower"] <= inner["quantile_effect_upper"]

    def test_frank_copula_bounds_are_finite(self):
        import math

        from polisyos.foundry.methods.catalog.causal.bounds import CopulaBoundsEstimator

        state = self._make_state(seed=5)
        result = CopulaBoundsEstimator.pure_step(state, {"n_eval_points": 50})
        inner = result["result"]
        assert math.isfinite(inner["ate_lower_bound"])
        assert math.isfinite(inner["ate_upper_bound"])
        assert math.isfinite(inner["quantile_effect_lower"])
        assert math.isfinite(inner["quantile_effect_upper"])


class TestTanBoundsEstimator:
    """Tests for Tan (2006) MSM sensitivity bounds (Phase 7)."""

    def _make_state(self, n: int = 400, seed: int = 42) -> dict:
        rng = np.random.default_rng(seed)
        T = rng.integers(0, 2, size=n).astype(float)
        Y = 0.5 * T + rng.normal(0, 0.3, size=n)
        return {"outcome": Y, "treatment": T}

    def test_sweep_runs_with_default_lambdas(self):
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import TanBoundsEstimator

        state = self._make_state()
        result = TanBoundsEstimator.pure_step(state, {})
        assert "result" in result
        assert "sweep" in result["result"]

    def test_sweep_has_correct_number_of_values(self):
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import TanBoundsEstimator
        from polisyos.ir.analytics.partial_identification import SensitivitySweepResult

        state = self._make_state()
        lambda_values = [1.0, 1.5, 2.0, 3.0]
        result = TanBoundsEstimator.pure_step(state, {"lambda_values": lambda_values})
        sweep = SensitivitySweepResult.model_validate(result["result"]["sweep"])
        assert len(sweep.parameter_values) == 4

    def test_bounds_widen_with_larger_lambda(self):
        """Bound widths must be non-decreasing in λ."""
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import TanBoundsEstimator
        from polisyos.ir.analytics.partial_identification import SensitivitySweepResult

        state = self._make_state()
        result = TanBoundsEstimator.pure_step(state, {"lambda_values": [1.0, 1.5, 2.0]})
        sweep = SensitivitySweepResult.model_validate(result["result"]["sweep"])
        widths = [
            sweep.upper_bounds[i] - sweep.lower_bounds[i]
            for i in range(len(sweep.parameter_values))
        ]
        for i in range(len(widths) - 1):
            assert widths[i] <= widths[i + 1] + 1e-6, (
                f"Width at λ={sweep.parameter_values[i]} ({widths[i]:.6f}) > "
                f"width at λ={sweep.parameter_values[i + 1]} ({widths[i + 1]:.6f})"
            )

    def test_at_lambda_1_contains_naive_ate(self):
        """At λ=1 the bounds should contain the naive ATE."""
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import TanBoundsEstimator

        state = self._make_state()
        Y = state["outcome"]
        T = state["treatment"]
        naive_ate = float(np.mean(Y[T > 0.5]) - np.mean(Y[T <= 0.5]))
        result = TanBoundsEstimator.pure_step(state, {"lambda_values": [1.0]})
        inner = result["result"]
        assert inner["ate_lower_bound"] <= naive_ate + 0.01
        assert inner["ate_upper_bound"] >= naive_ate - 0.01

    def test_sweep_serialization_roundtrip(self):
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import TanBoundsEstimator
        from polisyos.ir.analytics.partial_identification import SensitivitySweepResult

        state = self._make_state()
        result = TanBoundsEstimator.pure_step(state, {})
        sweep = SensitivitySweepResult.model_validate(result["result"]["sweep"])
        dumped = sweep.model_dump(mode="json")
        reloaded = SensitivitySweepResult.model_validate(dumped)
        assert reloaded.parameter_name == sweep.parameter_name
        assert len(reloaded.parameter_values) == len(sweep.parameter_values)


class TestIntersectionBoundsEstimator:
    """Tests for Chernozhukov-Lee-Rosen (2013) intersection bounds (Phase 7)."""

    def _make_bounds_list(self) -> list[dict]:
        return [
            {"ate_lower_bound": -0.3, "ate_upper_bound": 0.8, "se": 0.05},
            {"ate_lower_bound": -0.1, "ate_upper_bound": 0.6, "se": 0.04},
            {"ate_lower_bound": -0.2, "ate_upper_bound": 0.5, "se": 0.06},
        ]

    def test_intersection_is_max_lower_min_upper(self):
        """max(lowers) = -0.1, min(uppers) = 0.5."""
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
            IntersectionBoundsEstimator,
        )

        bounds_list = self._make_bounds_list()
        result = IntersectionBoundsEstimator.pure_step({"bounds_list": bounds_list}, {"n_obs": 300})
        inner = result["result"]
        assert abs(inner["ate_lower_bound"] - (-0.1)) < 1e-9
        assert abs(inner["ate_upper_bound"] - 0.5) < 1e-9

    def test_never_wider_than_individual_bounds(self):
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
            IntersectionBoundsEstimator,
        )

        bounds_list = self._make_bounds_list()
        result = IntersectionBoundsEstimator.pure_step({"bounds_list": bounds_list}, {"n_obs": 300})
        inner = result["result"]
        for b in bounds_list:
            assert inner["ate_lower_bound"] >= b["ate_lower_bound"] - 1e-9
            assert inner["ate_upper_bound"] <= b["ate_upper_bound"] + 1e-9

    def test_clr_bootstrap_produces_valid_ci(self):
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
            IntersectionBoundsEstimator,
        )

        bounds_list = self._make_bounds_list()
        result = IntersectionBoundsEstimator.pure_step(
            {"bounds_list": bounds_list},
            {"n_obs": 300, "use_clr_bootstrap": True, "n_bootstrap": 200, "seed": 42},
        )
        inner = result["result"]
        assert inner["ci_lower"] <= inner["ate_lower_bound"] + 1e-9
        assert inner["ci_upper"] >= inner["ate_upper_bound"] - 1e-9

    def test_partial_id_result_method_is_intersection_bounds(self):
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
            IntersectionBoundsEstimator,
        )
        from polisyos.ir.analytics.partial_identification import (
            BoundMethod,
            PartialIdentificationResult,
        )

        bounds_list = self._make_bounds_list()
        result = IntersectionBoundsEstimator.pure_step({"bounds_list": bounds_list}, {"n_obs": 300})
        pid = PartialIdentificationResult.model_validate(result["result"]["partial_id_result"])
        assert pid.method == BoundMethod.INTERSECTION_BOUNDS

    def test_single_bound_is_returned_unchanged(self):
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
            IntersectionBoundsEstimator,
        )

        bounds_list = [{"ate_lower_bound": -0.2, "ate_upper_bound": 0.7, "se": 0.05}]
        result = IntersectionBoundsEstimator.pure_step({"bounds_list": bounds_list}, {"n_obs": 300})
        inner = result["result"]
        assert abs(inner["ate_lower_bound"] - (-0.2)) < 1e-9
        assert abs(inner["ate_upper_bound"] - 0.7) < 1e-9


class TestRosenbaumSharpBoundsEstimator:
    """Tests for sharp per-γ p-value bounds (Phase 7)."""

    def _make_matched_diffs(self, n_pairs: int = 50, seed: int = 42) -> dict:
        rng = np.random.default_rng(seed)
        diffs = 0.3 + rng.normal(0, 0.2, size=n_pairs)
        return {"outcome": diffs}

    def test_sweep_runs_on_matched_diffs(self):
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
            RosenbaumSharpBoundsEstimator,
        )

        state = self._make_matched_diffs()
        result = RosenbaumSharpBoundsEstimator.pure_step(state, {"is_matched_diffs": True})
        assert "result" in result
        assert "sweep" in result["result"]

    def test_p_upper_monotone_in_gamma(self):
        """p_upper must be non-decreasing in Γ."""
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
            RosenbaumSharpBoundsEstimator,
        )
        from polisyos.ir.analytics.partial_identification import SensitivitySweepResult

        state = self._make_matched_diffs()
        gamma_values = [1.0, 1.5, 2.0, 2.5, 3.0]
        result = RosenbaumSharpBoundsEstimator.pure_step(
            state, {"is_matched_diffs": True, "gamma_values": gamma_values}
        )
        sweep = SensitivitySweepResult.model_validate(result["result"]["sweep"])
        uppers = list(sweep.upper_bounds)
        for i in range(len(uppers) - 1):
            assert uppers[i] <= uppers[i + 1] + 1e-6, (
                f"p_upper at Γ={gamma_values[i]} ({uppers[i]:.6f}) > "
                f"p_upper at Γ={gamma_values[i + 1]} ({uppers[i + 1]:.6f})"
            )

    def test_critical_gamma_greater_than_1_on_strong_effect(self):
        """With a strong positive effect, critical Γ must be > 1."""
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
            RosenbaumSharpBoundsEstimator,
        )

        rng = np.random.default_rng(0)
        # Large positive differences → strong evidence → critical Γ >> 1
        diffs = 0.8 + rng.normal(0, 0.1, size=60)
        result = RosenbaumSharpBoundsEstimator.pure_step(
            {"outcome": diffs},
            {"is_matched_diffs": True, "gamma_values": list(np.arange(1.0, 6.1, 0.5))},
        )
        critical = result["result"]["critical_gamma"]
        assert critical is None or critical > 1.0

    def test_sweep_serialization_roundtrip(self):
        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
            RosenbaumSharpBoundsEstimator,
        )
        from polisyos.ir.analytics.partial_identification import SensitivitySweepResult

        state = self._make_matched_diffs()
        result = RosenbaumSharpBoundsEstimator.pure_step(state, {"is_matched_diffs": True})
        sweep = SensitivitySweepResult.model_validate(result["result"]["sweep"])
        dumped = sweep.model_dump(mode="json")
        reloaded = SensitivitySweepResult.model_validate(dumped)
        assert reloaded.parameter_name == "gamma"
        assert len(reloaded.parameter_values) == len(sweep.parameter_values)
