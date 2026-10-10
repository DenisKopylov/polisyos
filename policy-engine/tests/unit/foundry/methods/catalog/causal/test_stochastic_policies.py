from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.causal.diagnostics import PolicyOverlapDiagnostic
from polisyos.foundry.methods.catalog.causal.stochastic_policies import (
    PolicyAIPWEstimator,
    PolicyPluginEstimator,
    PolicyTMLEEstimator,
)


def _binary_policy_dgp(seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = 800
    X = rng.normal(0.0, 1.0, size=(n, 2))
    logits = 0.6 * X[:, 0] - 0.4 * X[:, 1]
    propensity = 1.0 / (1.0 + np.exp(-logits))
    T = rng.binomial(1, propensity, size=n).astype(float)
    Y = 1.5 * T + 0.5 * X[:, 0] + rng.normal(0.0, 0.25, size=n)
    return Y, T, X


def _continuous_policy_dgp(seed: int = 123) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = 600
    X = rng.normal(0.0, 1.0, size=(n, 2))
    T = 0.7 * X[:, 0] - 0.2 * X[:, 1] + rng.normal(0.0, 0.5, size=n)
    Y = 2.0 + 1.3 * T + 0.4 * X[:, 0] + rng.normal(0.0, 0.25, size=n)
    return Y, T, X


def test_policy_aipw_accepts_explicit_policy_probabilities() -> None:
    Y, T, X = _binary_policy_dgp()
    result = PolicyAIPWEstimator.pure_step(
        {
            "X": X,
            "treatment": T,
            "outcome": Y,
            "policy_probabilities": np.full(len(Y), 0.75),
        },
        {},
    )

    assert np.isfinite(result["result"]["policy_value"])
    assert 0.8 < result["result"]["policy_value"] < 1.4
    assert len(result["policy_weights"]) == len(Y)


def test_incremental_policy_delta_one_tracks_observed_mean() -> None:
    Y, T, X = _binary_policy_dgp()
    aipw = PolicyAIPWEstimator.pure_step(
        {"X": X, "treatment": T, "outcome": Y},
        {"policy_expr": "incremental_odds(delta=1.0)"},
    )
    tmle = PolicyTMLEEstimator.pure_step(
        {"X": X, "treatment": T, "outcome": Y},
        {"policy_expr": "incremental_odds(delta=1.0)"},
    )

    observed_mean = float(np.mean(Y))
    assert abs(aipw["result"]["policy_value"] - observed_mean) < 0.2
    assert abs(tmle["result"]["policy_value"] - observed_mean) < 0.2


def test_policy_tmle_emits_targeting_summary_and_overlap_payload() -> None:
    Y, T, X = _binary_policy_dgp()
    result = PolicyTMLEEstimator.pure_step(
        {"X": X, "treatment": T, "outcome": Y},
        {"policy_expr": "incremental_odds(delta=1.5)"},
    )

    assert "targeting_summary" in result["result"]
    assert result["result"]["targeting_summary"]["n_iterations"] == 1
    assert len(result["policy_weights"]) == len(Y)

    diag = PolicyOverlapDiagnostic.pure_step(result, {})
    assert diag["result"]["status"] == "ok"
    assert diag["result"]["effective_sample_size"] > 0.0
    assert "gate_eligible" in diag["result"]


def test_policy_plugin_supports_gaussian_soft_policy_for_continuous_treatment() -> None:
    Y, T, X = _continuous_policy_dgp()
    result = PolicyPluginEstimator.pure_step(
        {"X": X, "treatment": T, "outcome": Y},
        {"policy_expr": "normal(mean=0.5, sd=0.3)"},
    )

    assert np.isfinite(result["result"]["policy_value"])
    assert result["result"]["policy_weights_available"] is True
    assert len(result["policy_weights"]) == len(Y)
    assert 0.2 < result["result"]["policy_treatment_mean"] < 0.8

    diag = PolicyOverlapDiagnostic.pure_step(result, {})
    assert diag["result"]["status"] == "ok"
    assert "top_1pct_weight_share" in diag["result"]
    assert "gate_eligible" in diag["result"]


def test_policy_overlap_empty_weights_reports_insufficient_inputs() -> None:
    diag = PolicyOverlapDiagnostic.pure_step({"policy_weights": []}, {})
    assert diag["result"]["status"] == "insufficient_inputs"
