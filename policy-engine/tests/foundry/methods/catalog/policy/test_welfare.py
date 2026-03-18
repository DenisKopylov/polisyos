from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.policy.welfare import (
    AtkinsonSWFEstimator,
    CostBenefitAnalysisEstimator,
    CostEffectivenessEstimator,
    RawlsianSWFEstimator,
    SenCapabilityEstimator,
    UtilitarianSWFEstimator,
)


class TestCostBenefitAnalysis:
    def test_positive_npv(self):
        state = {
            "benefits": np.array([0, 100, 200, 300]),
            "costs": np.array([500, 50, 50, 50]),
        }
        result = CostBenefitAnalysisEstimator.pure_step(state, {"discount_rate": 0.0})["result"]
        assert result["npv"] == pytest.approx(-50.0)
        assert result["bcr"] == pytest.approx(600.0 / 650.0, rel=1e-4)
        assert result["n_periods"] == 4

    def test_zero_discount_rate(self):
        state = {
            "benefits": np.array([100, 100]),
            "costs": np.array([50, 50]),
        }
        result = CostBenefitAnalysisEstimator.pure_step(state, {"discount_rate": 0.0})["result"]
        assert result["npv"] == pytest.approx(100.0)
        assert result["bcr"] == pytest.approx(2.0)

    def test_irr_found(self):
        state = {
            "benefits": np.array([0, 200, 200]),
            "costs": np.array([300, 0, 0]),
        }
        result = CostBenefitAnalysisEstimator.pure_step(state, {"discount_rate": 0.05})["result"]
        assert result["irr"] is not None
        assert result["irr"] > 0

    def test_shape_mismatch(self):
        with pytest.raises(ValueError, match="same length"):
            CostBenefitAnalysisEstimator.pure_step(
                {"benefits": np.array([1, 2]), "costs": np.array([1])}, {}
            )


class TestCostEffectiveness:
    def test_icer_computation(self):
        state = {
            "costs": np.array([100, 200, 150]),
            "effects": np.array([10, 30, 20]),
        }
        result = CostEffectivenessEstimator.pure_step(state, {"baseline_index": 0})["result"]
        assert result["icers"][0] is None  # baseline
        assert result["icers"][1] == pytest.approx(5.0)  # (200-100)/(30-10)


class TestSWFs:
    def test_utilitarian(self):
        result = UtilitarianSWFEstimator.pure_step(
            np.array([10, 20, 30]), {}
        )["result"]
        assert result["welfare"] == pytest.approx(60.0)
        assert result["mean_utility"] == pytest.approx(20.0)

    def test_rawlsian(self):
        result = RawlsianSWFEstimator.pure_step(
            np.array([10, 20, 30]), {}
        )["result"]
        assert result["welfare"] == pytest.approx(10.0)
        assert result["min_index"] == 0

    def test_atkinson_swf(self):
        values = np.array([10, 20, 30, 40, 50])
        result = AtkinsonSWFEstimator.pure_step(values, {"epsilon": 0.5})["result"]
        assert result["welfare"] > 0
        assert result["ede_income"] <= float(np.mean(values))

    def test_atkinson_swf_equal(self):
        values = np.array([100.0, 100.0, 100.0])
        result = AtkinsonSWFEstimator.pure_step(values, {"epsilon": 1.0})["result"]
        assert result["ede_income"] == pytest.approx(100.0, rel=1e-4)

    def test_sen_capability(self):
        # Equal distribution → Gini = 0 → welfare = mean
        values = np.array([100.0, 100.0, 100.0])
        result = SenCapabilityEstimator.pure_step(values, {})["result"]
        assert result["gini"] == pytest.approx(0.0, abs=1e-6)
        assert result["welfare"] == pytest.approx(100.0, abs=1e-4)

    def test_sen_unequal(self):
        values = np.array([0.0, 0.0, 0.0, 0.0, 100.0])
        result = SenCapabilityEstimator.pure_step(values, {})["result"]
        assert result["gini"] > 0.5
        assert result["welfare"] < float(np.mean(values))
