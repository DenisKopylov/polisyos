"""Tests for CrossFitOrchestrator inner_method_fqn dispatch."""
import numpy as np
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../src"))

from polisyos.foundry.methods.catalog.causal.cross_fit import CrossFitOrchestrator


def make_data(n=200, seed=42):
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, 3))
    T = (rng.standard_normal(n) + X[:, 0] > 0).astype(float)
    Y = 0.5 * T + X[:, 0] * 0.3 + rng.standard_normal(n) * 0.1
    return {"X": X, "treatment": T, "outcome": Y}


class TestCrossFitDispatch:
    def test_no_fqn_produces_finite_ate(self):
        state = make_data()
        result = CrossFitOrchestrator.pure_step(state, {"n_folds": 3, "seed": 0})
        assert np.isfinite(result["result"]["ate"])

    def test_aipw_fqn_produces_finite_ate(self):
        state = make_data()
        result = CrossFitOrchestrator.pure_step(
            state, {"n_folds": 3, "seed": 0, "inner_method_fqn": "causal.treatment_effects.aipw@1.0.0"}
        )
        assert np.isfinite(result["result"]["ate"])

    def test_dml_fqn_produces_finite_ate(self):
        state = make_data()
        result = CrossFitOrchestrator.pure_step(
            state, {"n_folds": 3, "seed": 0, "inner_method_fqn": "causal.hte.double_ml@1.0.0"}
        )
        assert np.isfinite(result["result"]["ate"])

    def test_tmle_fqn_produces_finite_ate(self):
        state = make_data()
        result = CrossFitOrchestrator.pure_step(
            state, {"n_folds": 3, "seed": 0, "inner_method_fqn": "causal.treatment_effects.tmle@1.0.0"}
        )
        assert np.isfinite(result["result"]["ate"])

    def test_ipw_fqn_produces_finite_ate(self):
        state = make_data()
        result = CrossFitOrchestrator.pure_step(
            state, {"n_folds": 3, "seed": 0, "inner_method_fqn": "causal.treatment_effects.ipw@1.0.0"}
        )
        assert np.isfinite(result["result"]["ate"])

    def test_unknown_fqn_falls_back_to_default(self):
        state = make_data()
        result_unknown = CrossFitOrchestrator.pure_step(
            state, {"n_folds": 3, "seed": 0, "inner_method_fqn": "unknown.method@9.9.9"}
        )
        result_default = CrossFitOrchestrator.pure_step(
            state, {"n_folds": 3, "seed": 0}
        )
        assert np.isfinite(result_unknown["result"]["ate"])
        assert abs(result_unknown["result"]["ate"] - result_default["result"]["ate"]) < 1e-6

    def test_result_contains_inner_method_fqn_key(self):
        state = make_data()
        fqn = "causal.treatment_effects.aipw@1.0.0"
        result = CrossFitOrchestrator.pure_step(
            state, {"n_folds": 3, "seed": 0, "inner_method_fqn": fqn}
        )
        assert "inner_method_fqn" in result["result"]
        assert result["result"]["inner_method_fqn"] == fqn

    def test_n_folds_respected(self):
        state = make_data(n=100)
        result = CrossFitOrchestrator.pure_step(state, {"n_folds": 4, "seed": 0})
        assert result["result"]["n_folds"] == 4
