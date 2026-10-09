"""Tests for bootstrap confidence intervals."""

from __future__ import annotations

import json
from dataclasses import asdict

import numpy as np
import pytest

from polisyos.scientist.methods.backtesting.bootstrap import (
    BootstrapCI,
    BootstrapValidationError,
    bootstrap_metric,
    bootstrap_scenario_metrics,
)


class TestBootstrapMetric:
    def test_mean_ci(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0] * 20
        ci = bootstrap_metric(values, metric="test", confidence_level=0.95, seed=42)
        assert ci.metric == "test"
        assert ci.lower <= ci.point_estimate <= ci.upper
        assert ci.confidence_level == 0.95
        assert abs(ci.point_estimate - 3.0) < 0.5

    def test_median_ci(self):
        values = [1.0, 2.0, 3.0, 100.0, 5.0] * 20
        ci = bootstrap_metric(values, metric="m", statistic="median", seed=42)
        assert ci.lower <= ci.point_estimate <= ci.upper
        assert ci.point_estimate == 3.0

    def test_empty_values(self):
        with pytest.raises(BootstrapValidationError, match="at least one observed value"):
            bootstrap_metric([], metric="empty")

    def test_zero_bootstrap_count_is_rejected(self):
        with pytest.raises(BootstrapValidationError, match="greater than zero"):
            bootstrap_metric([1.0, 2.0], n_bootstrap=0)

    def test_single_value(self):
        ci = bootstrap_metric([5.0], metric="single", seed=42)
        assert ci.point_estimate == 5.0

    def test_reproducibility(self):
        values = list(range(50))
        ci1 = bootstrap_metric(values, seed=123)
        ci2 = bootstrap_metric(values, seed=123)
        assert ci1.lower == ci2.lower
        assert ci1.upper == ci2.upper

    def test_unknown_statistic_is_rejected_instead_of_defaulting_to_mean(self):
        with pytest.raises(BootstrapValidationError, match="statistic"):
            bootstrap_metric(
                [0.0, 0.0, 9.0],
                statistic="medain",
                n_bootstrap=1,
                seed=42,
            )

    @pytest.mark.parametrize("entrypoint", ["metric", "scenario"])
    def test_two_dimensional_observations_refuse_before_callback_or_rng(self, monkeypatch, entrypoint):
        callback_calls = 0
        rng_calls = []

        def forbidden_rng(seed=None):
            rng_calls.append(seed)
            raise AssertionError("invalid observations reached RNG construction")

        def statistic(values):
            nonlocal callback_calls
            callback_calls += 1
            return float(np.mean(values))

        monkeypatch.setattr(np.random, "default_rng", forbidden_rng)
        values = np.array([[1.0, 2.0], [3.0, 4.0]])

        error = None
        try:
            if entrypoint == "metric":
                bootstrap_metric(values, statistic=statistic, n_bootstrap=2, seed=42)
            else:
                bootstrap_scenario_metrics(values, n_bootstrap=2, seed=42)
        except Exception as exc:
            error = exc

        assert callback_calls == 0
        assert rng_calls == []
        assert isinstance(error, BootstrapValidationError)
        assert error.code == "invalid_dimensions"

    def test_unknown_statistic_refuses_before_rng_construction(self, monkeypatch):
        rng_calls = []

        def forbidden_rng(seed=None):
            rng_calls.append(seed)
            raise AssertionError("unknown statistic reached RNG construction")

        monkeypatch.setattr(np.random, "default_rng", forbidden_rng)

        with pytest.raises(BootstrapValidationError) as error:
            bootstrap_metric([1.0, 2.0], statistic="medain", n_bootstrap=1, seed=42)

        assert error.value.code == "unknown_statistic"
        assert rng_calls == []

    @pytest.mark.parametrize("non_finite", [np.nan, np.inf])
    def test_non_finite_observations_are_rejected(self, non_finite):
        with pytest.raises(BootstrapValidationError, match="finite"):
            bootstrap_metric([1.0, non_finite], n_bootstrap=1, seed=42)

    def test_non_finite_statistic_output_is_rejected(self):
        def non_finite_statistic(_values):
            return float("nan")

        with pytest.raises(BootstrapValidationError, match="finite"):
            bootstrap_metric(
                [1.0, 2.0],
                statistic=non_finite_statistic,
                n_bootstrap=1,
                seed=42,
            )

    def test_callable_exception_type_is_preserved(self):
        def raising_statistic(_values):
            raise TypeError("caller-owned statistic failure")

        with pytest.raises(TypeError, match="caller-owned statistic failure"):
            bootstrap_metric(
                [1.0, 2.0],
                statistic=raising_statistic,
                n_bootstrap=1,
                seed=42,
            )

    @pytest.mark.parametrize(("statistic", "expected"), [("mean", 3.0), ("median", 0.0)])
    def test_executed_named_statistic_survives_consumer_readback(
        self, tmp_path, statistic, expected
    ):
        ci = bootstrap_metric(
            [0.0, 0.0, 9.0],
            metric="same_display_name",
            statistic=statistic,
            n_bootstrap=20,
            seed=42,
        )
        output = tmp_path / "bootstrap.json"
        output.write_text(json.dumps(asdict(ci)), encoding="utf-8")
        reopened = BootstrapCI(**json.loads(output.read_text(encoding="utf-8")))

        assert reopened.metric == "same_display_name"
        assert reopened.point_estimate == expected
        assert reopened.statistic == statistic
        assert reopened.statistic_identity_basis == "recomputed"

    def test_same_named_callables_keep_declared_identity_and_its_limit(self, tmp_path):
        def quantile_statistic(quantile):
            def statistic(values):
                return float(np.quantile(values, quantile))

            return statistic

        median = quantile_statistic(0.5)
        maximum = quantile_statistic(1.0)
        assert median.__qualname__ == maximum.__qualname__
        results = [
            bootstrap_metric(
                [0.0, 0.0, 9.0],
                metric="same_display_name",
                statistic=statistic,
                statistic_id=statistic_id,
                n_bootstrap=20,
                seed=42,
            )
            for statistic, statistic_id in [(median, "quantile:0.5"), (maximum, "quantile:1.0")]
        ]
        output = tmp_path / "custom-bootstrap.json"
        output.write_text(json.dumps([asdict(ci) for ci in results]), encoding="utf-8")
        reopened = [
            BootstrapCI(**payload) for payload in json.loads(output.read_text(encoding="utf-8"))
        ]

        assert [ci.point_estimate for ci in reopened] == [0.0, 9.0]
        assert [ci.statistic for ci in reopened] == ["quantile:0.5", "quantile:1.0"]
        assert {ci.statistic_identity_basis for ci in reopened} == {"consumer_asserted"}

        # The helper cannot establish arbitrary callable semantics from a name,
        # code address, or even a caller's duplicate declaration.
        undeclared = [
            bootstrap_metric([0.0, 0.0, 9.0], statistic=fn, n_bootstrap=1, seed=42)
            for fn in (median, maximum)
        ]
        assert [ci.point_estimate for ci in undeclared] == [0.0, 9.0]
        assert all(ci.statistic is None for ci in undeclared)
        assert {ci.statistic_identity_basis for ci in undeclared} == {"not_established"}
        duplicate_ids = [
            bootstrap_metric(
                [0.0, 0.0, 9.0],
                statistic=fn,
                statistic_id="same-declaration",
                n_bootstrap=1,
                seed=42,
            )
            for fn in (median, maximum)
        ]
        assert [ci.point_estimate for ci in duplicate_ids] == [0.0, 9.0]
        assert {ci.statistic_identity_basis for ci in duplicate_ids} == {"consumer_asserted"}

    @pytest.mark.parametrize("statistic_id", ["", "  ", 7])
    def test_invalid_callable_identity_is_rejected_before_statistic_execution(self, statistic_id):
        def forbidden_statistic(_values):
            raise AssertionError("invalid identity reached expensive statistical work")

        with pytest.raises(BootstrapValidationError, match="statistic_id"):
            bootstrap_metric(
                [1.0, 2.0], statistic=forbidden_statistic, statistic_id=statistic_id, n_bootstrap=1
            )

    def test_named_statistic_cannot_be_relabelled_by_callable_identity(self):
        with pytest.raises(BootstrapValidationError, match="statistic_id"):
            bootstrap_metric(
                [0.0, 0.0, 9.0], statistic="mean", statistic_id="median", n_bootstrap=1
            )


class TestBootstrapScenarioMetrics:
    def test_produces_mae_and_rmse(self):
        errors = np.random.default_rng(42).normal(0, 1, size=100).tolist()
        results = bootstrap_scenario_metrics(errors, seed=42)
        assert "mae" in results
        assert "rmse" in results
        assert results["mae"].lower <= results["mae"].upper
        assert results["rmse"].lower <= results["rmse"].upper

    def test_rmse_ci_bootstraps_rmse_directly(self):
        errors = [0.0, 1.0, 3.0, 9.0]
        seed = 7
        n_bootstrap = 200
        result = bootstrap_scenario_metrics(
            errors,
            seed=seed,
            n_bootstrap=n_bootstrap,
        )["rmse"]

        rng = np.random.default_rng(seed)
        arr = np.asarray(errors, dtype=float)
        boot_stats = np.empty(n_bootstrap)
        for idx in range(n_bootstrap):
            sample = rng.choice(arr, size=arr.size, replace=True)
            boot_stats[idx] = float(np.sqrt(np.mean(sample**2)))

        alpha = 0.05
        expected_lower = float(np.percentile(boot_stats, 100 * alpha / 2))
        expected_upper = float(np.percentile(boot_stats, 100 * (1 - alpha / 2)))

        assert result.point_estimate == float(np.sqrt(np.mean(arr**2)))
        assert result.lower == expected_lower
        assert result.upper == expected_upper
        assert result.statistic == "root_mean_square"
        assert result.statistic_identity_basis == "consumer_asserted"
