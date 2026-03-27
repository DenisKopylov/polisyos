"""Tests for bootstrap confidence intervals."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.scientist.backtesting.bootstrap import (
    BootstrapCI,
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
        ci = bootstrap_metric([], metric="empty")
        assert ci.point_estimate == 0.0
        assert ci.lower == 0.0
        assert ci.upper == 0.0

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
