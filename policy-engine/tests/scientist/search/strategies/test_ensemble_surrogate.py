"""Tests for WS6.6 — Ensemble Surrogate (GP + RF)."""

from __future__ import annotations

import math

import pytest

from polisyos.scientist.search.strategies.ensemble_surrogate import EnsembleSurrogate


# ---------------------------------------------------------------------------
# Construction & availability
# ---------------------------------------------------------------------------


class TestEnsembleSurrogateInit:
    def test_default_weights(self):
        es = EnsembleSurrogate(space_dim=2)
        assert es._gp_weight == pytest.approx(0.6)
        assert es._rf_weight == pytest.approx(0.4)

    def test_custom_weights(self):
        es = EnsembleSurrogate(space_dim=3, gp_weight=0.8)
        assert es._gp_weight == pytest.approx(0.8)
        assert es._rf_weight == pytest.approx(0.2)

    def test_is_ready_at_least_one(self):
        es = EnsembleSurrogate(space_dim=1)
        # Must have at least one backend or is_ready is False
        # (sklearn usually available in test env)
        # Just verify the property doesn't crash
        assert isinstance(es.is_ready, bool)


# ---------------------------------------------------------------------------
# RF-only predictions (sklearn usually available)
# ---------------------------------------------------------------------------


class TestRFOnlyPrediction:
    @pytest.fixture
    def rf_surrogate(self):
        es = EnsembleSurrogate(space_dim=1, gp_weight=0.6)
        if not es._rf_ready:
            pytest.skip("sklearn not available")
        # Force GP unavailable to test RF-only path
        es._gp_ready = False
        return es

    def test_fit_and_predict(self, rf_surrogate):
        X = [[float(i)] for i in range(20)]
        y = [float(i) * 2.0 for i in range(20)]
        rf_surrogate.fit(X, y)
        means, stds = rf_surrogate.predict([[5.0], [10.0]])
        assert len(means) == 2
        assert len(stds) == 2
        # RF should approximate the linear relationship
        assert means[1] > means[0]

    def test_predict_returns_positive_std(self, rf_surrogate):
        X = [[float(i)] for i in range(20)]
        y = [float(i) ** 2 for i in range(20)]
        rf_surrogate.fit(X, y)
        _, stds = rf_surrogate.predict([[5.0]])
        assert all(s >= 0.0 for s in stds)

    def test_single_point_prediction(self, rf_surrogate):
        X = [[float(i)] for i in range(10)]
        y = [1.0] * 10
        rf_surrogate.fit(X, y)
        means, stds = rf_surrogate.predict([[5.0]])
        assert len(means) == 1
        assert means[0] == pytest.approx(1.0, abs=0.2)


# ---------------------------------------------------------------------------
# No-backend fallback
# ---------------------------------------------------------------------------


class TestNoBackendFallback:
    def test_predict_no_models_returns_defaults(self):
        es = EnsembleSurrogate(space_dim=1)
        es._gp_ready = False
        es._rf_ready = False
        es._gp = None
        es._rf = None
        means, stds = es.predict([[1.0], [2.0]])
        assert means == [0.0, 0.0]
        assert stds == [1.0, 1.0]


# ---------------------------------------------------------------------------
# Ensemble combination (both GP + RF)
# ---------------------------------------------------------------------------


class TestEnsembleCombination:
    def test_weighted_combination_with_rf(self):
        """Test that when only RF is available, predictions match RF."""
        es = EnsembleSurrogate(space_dim=1, gp_weight=0.6)
        if not es._rf_ready:
            pytest.skip("sklearn not available")
        es._gp_ready = False

        X = [[float(i)] for i in range(20)]
        y = [float(i) for i in range(20)]
        es.fit(X, y)

        means_ens, _ = es.predict([[10.0]])
        # With only RF, should get RF prediction
        assert len(means_ens) == 1
        assert means_ens[0] > 0  # Should be positive for x=10

    def test_fit_does_not_crash_with_both_unavailable(self):
        es = EnsembleSurrogate(space_dim=1)
        es._gp_ready = False
        es._rf_ready = False
        # Should not raise
        es.fit([[1.0]], [1.0])
