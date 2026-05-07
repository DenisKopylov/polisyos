"""Tests for inverse probability weighting."""

from __future__ import annotations

import numpy as np
from polisyos.scientist.methods.backtesting.ipw import (
    IPWResult,
    compute_propensity_weights,
    ipw_estimate,
)


class TestComputePropensityWeights:
    def test_basic_weights(self):
        rng = np.random.default_rng(42)
        n = 100
        treatment = rng.integers(0, 2, size=n)
        covariates = rng.normal(0, 1, size=(n, 2))
        weights = compute_propensity_weights(treatment, covariates)
        assert weights.shape == (n,)
        assert np.all(weights >= 0.01)
        assert np.all(weights <= 0.99)

    def test_clipping(self):
        treatment = np.array([1, 0, 1, 0])
        covariates = np.array([[10.0], [-10.0], [10.0], [-10.0]])
        weights = compute_propensity_weights(
            treatment,
            covariates,
            clip_min=0.1,
            clip_max=0.9,
        )
        assert np.all(weights >= 0.1)
        assert np.all(weights <= 0.9)


class TestIPWEstimate:
    def test_basic_ate(self):
        rng = np.random.default_rng(42)
        n = 200
        treatment = np.array([1] * 100 + [0] * 100)
        outcomes = np.concatenate(
            [
                rng.normal(5.0, 1.0, size=100),
                rng.normal(3.0, 1.0, size=100),
            ]
        )
        ps = np.full(n, 0.5)
        result = ipw_estimate(outcomes, treatment, ps)
        assert isinstance(result, IPWResult)
        assert result.ipw_estimate > 0  # treatment effect is positive
        assert result.effective_sample_size > 0

    def test_equal_propensity(self):
        outcomes = [1.0, 2.0, 3.0, 4.0]
        treatment = [1, 1, 0, 0]
        ps = np.array([0.5, 0.5, 0.5, 0.5])
        result = ipw_estimate(outcomes, treatment, ps)
        # With equal propensity, IPW = raw
        assert abs(result.ipw_estimate - result.raw_estimate) < 0.01

    def test_diagnostics(self):
        outcomes = np.arange(10, dtype=float)
        treatment = [1, 0] * 5
        ps = np.array([0.3, 0.7] * 5)
        result = ipw_estimate(outcomes, treatment, ps)
        assert result.max_weight > 0
        assert result.weight_variance >= 0
