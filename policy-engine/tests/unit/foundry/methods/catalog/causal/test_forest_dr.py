from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.catalog.causal.forest_dr import ForestDRLearnerEstimator
from polisyos.ir.analytics.causal import CausalMethod


def _make_hte_data(n: int = 250, seed: int = 0) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 4))
    e = 1.0 / (1.0 + np.exp(-(0.7 * X[:, 0] - 0.4 * X[:, 1])))
    T = rng.binomial(1, np.clip(e, 0.05, 0.95)).astype(float)
    tau = 0.4 + 0.7 * X[:, 2]
    mu = 1.3 * X[:, 0] - 0.6 * X[:, 3]
    Y = mu + tau * T + rng.normal(scale=0.35, size=n)
    return {"outcome": Y, "treatment": T, "covariates": X}


def test_forest_dr_gracefully_fails_without_backend():
    state = _make_hte_data()
    result = ForestDRLearnerEstimator.pure_step(state, {"__seed__": 7})
    report = result["report"]
    assert report.method == CausalMethod.FOREST_DR
    assert report.status.value in {"success", "numerical_failure"}


def test_forest_dr_output_shape_when_backend_available_or_graceful_failure():
    state = _make_hte_data(n=180, seed=3)
    result = ForestDRLearnerEstimator.pure_step(
        state,
        {
            "__seed__": 11,
            "n_estimators": 64,
            "cv_folds": 2,
            "subforest_size": 2,
        },
    )
    report = result["report"]
    assert report.method == CausalMethod.FOREST_DR
    if report.status.value == "success":
        hte_result = result["hte_result"]
        assert len(hte_result.cate_values) == 180
        assert np.isfinite(hte_result.ate)
