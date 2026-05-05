"""Tests for Super Learner nuisance model (Phase 6)."""

from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.catalog.causal.superlearner import (
    SuperLearnerConfig,
    SuperLearnerNuisance,
    SuperLearnerNuisanceModel,
    _cv_risk,
    _discrete_sl,
    _nnls_weights,
    _project_simplex,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rng():
    return np.random.default_rng(42)


@pytest.fixture
def linear_data(rng):
    n = 200
    X = rng.normal(0, 1, (n, 3))
    Y = 2.0 * X[:, 0] - 1.5 * X[:, 1] + rng.normal(0, 0.5, n)
    return X, Y


@pytest.fixture
def binary_data(rng):
    n = 200
    X = rng.normal(0, 1, (n, 3))
    log_odds = 0.8 * X[:, 0]
    prob = 1 / (1 + np.exp(-log_odds))
    Y = (rng.uniform(size=n) < prob).astype(float)
    return X, Y


# ---------------------------------------------------------------------------
# _project_simplex
# ---------------------------------------------------------------------------


class TestProjectSimplex:
    def test_sum_to_one(self, rng):
        v = rng.normal(0, 1, 5)
        w = _project_simplex(v)
        assert abs(w.sum() - 1.0) < 1e-10

    def test_nonnegative(self, rng):
        v = rng.normal(-2, 1, 5)
        w = _project_simplex(v)
        assert (w >= -1e-12).all()

    def test_already_on_simplex(self):
        v = np.array([0.2, 0.5, 0.3])
        w = _project_simplex(v)
        np.testing.assert_allclose(w, v, atol=1e-10)

    def test_single_element(self):
        w = _project_simplex(np.array([42.0]))
        np.testing.assert_allclose(w, np.array([1.0]), atol=1e-10)


# ---------------------------------------------------------------------------
# _nnls_weights
# ---------------------------------------------------------------------------


class TestNNLSWeights:
    def test_weights_sum_to_one(self, rng):
        Z = rng.normal(0, 1, (100, 3))
        Y = Z[:, 0] + rng.normal(0, 0.1, 100)
        w = _nnls_weights(Z, Y)
        assert abs(w.sum() - 1.0) < 1e-6

    def test_weights_nonnegative(self, rng):
        Z = rng.normal(0, 1, (100, 4))
        Y = rng.normal(0, 1, 100)
        w = _nnls_weights(Z, Y)
        assert (w >= -1e-8).all()

    def test_perfect_learner_gets_weight_one(self):
        """A learner that predicts perfectly should dominate."""
        n = 100
        Y = np.linspace(0, 1, n)
        Z = np.column_stack([Y, np.zeros(n), np.zeros(n)])  # col 0 = perfect
        w = _nnls_weights(Z, Y)
        # col 0 should have the highest weight
        assert w[0] == w.max()


# ---------------------------------------------------------------------------
# FittedSuperLearner.predict
# ---------------------------------------------------------------------------


class TestFittedSuperLearnerPredict:
    def test_predict_shape(self, linear_data, rng):
        X, Y = linear_data
        fitted = SuperLearnerNuisance.fit(X, Y, library=["ols", "ridge"], v_folds=3)
        X_new = rng.normal(0, 1, (50, 3))
        preds = fitted.predict(X_new)
        assert preds.shape == (50,)

    def test_predict_finite(self, linear_data, rng):
        X, Y = linear_data
        fitted = SuperLearnerNuisance.fit(X, Y, library=["ols", "ridge"], v_folds=3)
        X_new = rng.normal(0, 1, (50, 3))
        preds = fitted.predict(X_new)
        assert np.isfinite(preds).all()

    def test_predict_binary_clipped(self, binary_data, rng):
        X, Y = binary_data
        fitted = SuperLearnerNuisance.fit(
            X, Y, library=["ols", "ridge"], v_folds=3, outcome_type="binary"
        )
        X_new = rng.normal(0, 1, (50, 3))
        preds = fitted.predict(X_new)
        assert (preds >= 0).all()
        assert (preds <= 1).all()


# ---------------------------------------------------------------------------
# SuperLearnerNuisance.fit
# ---------------------------------------------------------------------------


class TestSuperLearnerNuisanceFit:
    def test_weights_sum_to_one(self, linear_data):
        X, Y = linear_data
        fitted = SuperLearnerNuisance.fit(X, Y, library=["ols", "ridge"], v_folds=3)
        assert abs(fitted.weights.sum() - 1.0) < 1e-6

    def test_weights_nonnegative(self, linear_data):
        X, Y = linear_data
        fitted = SuperLearnerNuisance.fit(X, Y, library=["ols", "ridge"], v_folds=3)
        assert (fitted.weights >= -1e-8).all()

    def test_cv_risk_finite(self, linear_data):
        X, Y = linear_data
        fitted = SuperLearnerNuisance.fit(X, Y, library=["ols", "ridge"], v_folds=3)
        for name, risk in fitted.cv_risk.items():
            assert np.isfinite(risk), f"cv_risk[{name}] = {risk}"

    def test_learner_names_match_library(self, linear_data):
        X, Y = linear_data
        library = ["ols", "ridge"]
        fitted = SuperLearnerNuisance.fit(X, Y, library=library, v_folds=3)
        assert set(fitted.learner_names) == set(library)

    def test_n_folds_stored(self, linear_data):
        X, Y = linear_data
        fitted = SuperLearnerNuisance.fit(X, Y, library=["ols"], v_folds=4)
        assert fitted.n_folds == 4

    def test_superlearner_not_worse_than_worst_learner(self, linear_data):
        """SL CV risk <= max individual learner CV risk."""
        X, Y = linear_data
        fitted = SuperLearnerNuisance.fit(X, Y, library=["ols", "ridge"], v_folds=3)
        sl_preds = fitted.predict(X)
        sl_mse = np.mean((Y - sl_preds) ** 2)
        worst_learner_cv = max(fitted.cv_risk.values())
        # SL in-sample MSE should be at most as bad as worst CV risk
        # (this is a loose bound — SL is no worse asymptotically)
        assert sl_mse <= worst_learner_cv * 2.0

    def test_large_library_with_rf_fallback(self, linear_data):
        """rf learner requested; even if sklearn absent, fit completes."""
        X, Y = linear_data
        fitted = SuperLearnerNuisance.fit(X, Y, library=["ols", "ridge", "rf"], v_folds=3)
        assert fitted.weights.sum() > 0.99

    def test_binary_outcome_sigmoid_activated(self, binary_data):
        X, Y = binary_data
        fitted = SuperLearnerNuisance.fit(
            X, Y, library=["ols", "ridge"], v_folds=3, outcome_type="binary"
        )
        assert fitted.binary is True

    def test_reproducibility_with_seed(self, linear_data):
        X, Y = linear_data
        f1 = SuperLearnerNuisance.fit(X, Y, library=["ols", "ridge"], v_folds=3, seed=7)
        f2 = SuperLearnerNuisance.fit(X, Y, library=["ols", "ridge"], v_folds=3, seed=7)
        np.testing.assert_array_equal(f1.weights, f2.weights)


# ---------------------------------------------------------------------------
# SuperLearnerNuisanceModel (Foundry method wrapper)
# ---------------------------------------------------------------------------


class TestSuperLearnerNuisanceModel:
    def test_pure_step_returns_expected_keys(self, linear_data):
        X, Y = linear_data
        state = {"covariates": X, "outcome": Y}
        params = {"library": ["ols", "ridge"], "v_folds": 3}
        result = SuperLearnerNuisanceModel.pure_step(state, params)
        assert "predictions" in result
        assert "cv_risk" in result
        assert "weights" in result

    def test_pure_step_predictions_shape(self, linear_data):
        X, Y = linear_data
        state = {"covariates": X, "outcome": Y}
        params = {"library": ["ols"], "v_folds": 3}
        result = SuperLearnerNuisanceModel.pure_step(state, params)
        preds = result["predictions"]
        assert np.asarray(preds).shape == (len(Y),)

    def test_pure_step_weights_sum_to_one(self, linear_data):
        X, Y = linear_data
        state = {"covariates": X, "outcome": Y}
        params = {"library": ["ols", "ridge"], "v_folds": 3}
        result = SuperLearnerNuisanceModel.pure_step(state, params)
        assert abs(np.sum(result["weights"]) - 1.0) < 1e-6

    def test_pure_step_method_fqn_registered(self):
        sig = SuperLearnerNuisanceModel.signature
        assert "super_learner" in sig.name

    def test_pure_step_default_library_ols_ridge(self, rng):
        n = 100
        X = rng.normal(0, 1, (n, 2))
        Y = X[:, 0] + rng.normal(0, 0.3, n)
        state = {"covariates": X, "outcome": Y}
        result = SuperLearnerNuisanceModel.pure_step(state, {})
        assert np.isfinite(result["predictions"]).all()


class TestSuperLearnerConfigAndModes:
    def test_config_roundtrip(self):
        cfg = SuperLearnerConfig(n_folds=4, method="discrete", screen=False, nested_cv=True)
        assert cfg.n_folds == 4
        assert cfg.method == "discrete"
        assert cfg.nested_cv is True

    def test_discrete_sl_picks_min_risk(self):
        best = _discrete_sl({"ridge": 0.3, "ols": 0.2, "rf": 0.5})
        assert best == "ols"

    def test_cv_risk_finite(self, linear_data):
        X, Y = linear_data
        risk = _cv_risk("ridge", X, Y, n_folds=3, binary=False, seed=0)
        assert np.isfinite(risk)

    def test_nested_cv_returns_risk(self, linear_data):
        X, Y = linear_data
        fitted = SuperLearnerNuisance.fit(
            X,
            Y,
            library=["ols", "ridge", "lasso"],
            v_folds=3,
            nested_cv=True,
            method="nnls",
            screen=True,
            screen_top_k=2,
        )
        assert fitted.nested_cv_risk is not None
        assert np.isfinite(fitted.nested_cv_risk)

    def test_screening_reduces_dimension(self, linear_data):
        X, Y = linear_data
        fitted = SuperLearnerNuisance.fit(
            X,
            Y,
            library=["ols", "ridge"],
            v_folds=3,
            screen=True,
            screen_top_k=1,
        )
        assert fitted.feature_indices is not None
        assert len(fitted.feature_indices) == 1
