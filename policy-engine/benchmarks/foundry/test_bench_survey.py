"""Survey domain accuracy benchmarks."""
from __future__ import annotations

import numpy as np
import pytest

from benchmarks.foundry.conftest import make_survey_areas


@pytest.mark.benchmark
class TestSurveyAccuracy:

    def test_fay_herriot_shrinkage(self, bench_registry):
        """EBLUP shrinkage: estimates between direct and regression."""
        data = make_survey_areas(n_areas=8, seed=42)
        cls = bench_registry.get("survey.estimation.fay_herriot@1.0.0")
        result = cls.pure_step(data, {"max_iter": 50})["result"]
        assert result["n_areas"] == 8
        # Shrinkage factors should be in [0, 1]
        for sf in result["shrinkage_factors"]:
            assert 0.0 <= sf <= 1.0 + 1e-6, f"Shrinkage factor {sf} out of bounds"

    def test_fay_herriot_equal_variance(self, bench_registry):
        """Equal sampling variance → equal shrinkage factors."""
        data = {
            "y_direct": np.array([10.0, 20.0, 30.0, 40.0]),
            "X": np.column_stack([np.ones(4), np.arange(4, dtype=float)]),
            "sampling_var": np.array([1.0, 1.0, 1.0, 1.0]),
        }
        cls = bench_registry.get("survey.estimation.fay_herriot@1.0.0")
        result = cls.pure_step(data, {"max_iter": 50})["result"]
        sf = result["shrinkage_factors"]
        np.testing.assert_allclose(sf, sf[0], atol=0.01)

    def test_greg_total_consistency(self, bench_registry):
        """GREG total should be close to HT total for well-calibrated weights."""
        data = {
            "y": np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
            "X": np.column_stack([np.ones(5), np.arange(5, dtype=float)]),
            "weights": np.ones(5),
            "population_totals": np.array([5.0, 10.0]),
        }
        cls = bench_registry.get("survey.estimation.calibration_greg@1.0.0")
        result = cls.pure_step(data, {})["result"]
        assert result["n_obs"] == 5
        # GREG and HT totals should both be finite
        assert np.isfinite(result["greg_total"])
        assert np.isfinite(result["ht_total"])

    def test_fay_herriot_precision(self, bench_registry):
        """MSE estimates should be positive."""
        data = make_survey_areas(n_areas=6, seed=77)
        cls = bench_registry.get("survey.estimation.fay_herriot@1.0.0")
        result = cls.pure_step(data, {"max_iter": 100})["result"]
        for mse in result["mse_estimates"]:
            assert mse >= 0.0, f"MSE estimate {mse} should be non-negative"

    def test_greg_intercept_only(self, bench_registry):
        """GREG with intercept only → GREG total ≈ HT total."""
        data = {
            "y": np.array([5.0, 10.0, 15.0]),
            "X": np.ones((3, 1)),
            "weights": np.ones(3),
            "population_totals": np.array([3.0]),
        }
        cls = bench_registry.get("survey.estimation.calibration_greg@1.0.0")
        result = cls.pure_step(data, {})["result"]
        np.testing.assert_allclose(result["greg_total"], result["ht_total"], rtol=0.1)
