"""Tests for bootstrap confidence intervals."""

from __future__ import annotations

import numpy as np
import pytest
from polisyos.scientist.methods.backtesting.bootstrap import (
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
