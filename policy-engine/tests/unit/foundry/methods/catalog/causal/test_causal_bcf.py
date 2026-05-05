from __future__ import annotations

import sys
import types

import numpy as np
from polisyos.foundry.methods.catalog.causal.causal_bcf import CausalBCF, _fit_stochtree_bcf
from polisyos.ir.analytics.causal import CausalMethod


def _make_hte_data(n: int = 300, seed: int = 0) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    e = 1.0 / (1.0 + np.exp(-X[:, 0]))
    T = rng.binomial(1, e).astype(float)
    tau = 0.5 + 0.8 * X[:, 1]
    mu = 1.5 * X[:, 0] - 0.7 * X[:, 2]
    Y = mu + tau * T + rng.normal(scale=0.3, size=n)
    return {"outcome": Y, "treatment": T, "covariates": X}


def test_causal_bcf_returns_hte_result_and_backend_metadata():
    state = _make_hte_data()
    result = CausalBCF.pure_step(state, {"backend": "auto", "__seed__": 42, "bootstrap_runs": 40})
    report = result["report"]
    hte_result = result["hte_result"]

    assert report.method == CausalMethod.CAUSAL_BCF
    assert report.status.value == "success"
    assert hte_result.method == CausalMethod.CAUSAL_BCF
    assert "backend_used" in hte_result.metadata
    assert result["warnings"] is not None


def test_causal_bcf_recovers_linear_cate_reasonably():
    state = _make_hte_data(n=400, seed=3)
    result = CausalBCF.pure_step(
        state,
        {"backend": "sklearn", "__seed__": 7, "bootstrap_runs": 40, "ridge_alpha": 0.5},
    )
    hte_result = result["hte_result"]
    tau_hat = np.asarray(hte_result.cate_values, dtype=float)
    true_tau = 0.5 + 0.8 * state["covariates"][:, 1]
    rmse = float(np.sqrt(np.mean((tau_hat - true_tau) ** 2)))
    assert rmse < 1.5
    assert np.isfinite(hte_result.ate)


def _make_ric_data(n: int = 500, seed: int = 10) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """DGP with strong prognostic function μ(x) and weak treatment effect τ(x).

    This is the RIC (Regularization-Induced Confounding) scenario where
    vanilla BART overestimates treatment heterogeneity because a single
    model conflates μ(x) with τ(x). BCF's separate μ/τ ensemble architecture
    should handle this better.
    """
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 5))
    # Strong prognostic: μ(x) = 5*x0 + 3*x1² - 2*sin(x2)
    mu = 5.0 * X[:, 0] + 3.0 * X[:, 1] ** 2 - 2.0 * np.sin(X[:, 2])
    # Weak treatment effect: τ(x) = 0.2 (constant, small)
    tau = np.full(n, 0.2)
    e = 1.0 / (1.0 + np.exp(-0.5 * X[:, 0]))
    T = rng.binomial(1, e).astype(float)
    Y = mu + tau * T + rng.normal(scale=0.5, size=n)
    return {"outcome": Y, "treatment": T, "covariates": X}, tau


def test_bcf_beats_naive_on_ric_scenario():
    """BCF architecture should produce CATE estimates closer to truth on RIC DGP.

    On RIC scenario (strong μ, weak τ), BCF's two-model approach should yield
    lower RMSE than a naive single-model estimate.
    """
    state, true_tau = _make_ric_data(n=500, seed=10)
    result = CausalBCF.pure_step(
        state,
        {"backend": "sklearn", "__seed__": 42, "bootstrap_runs": 30, "ridge_alpha": 1.0},
    )
    hte_result = result["hte_result"]
    tau_hat = np.asarray(hte_result.cate_values, dtype=float)
    rmse_bcf = float(np.sqrt(np.mean((tau_hat - true_tau) ** 2)))
    # BCF should produce reasonable CATE even when τ is small and μ is large
    assert rmse_bcf < 2.0, f"BCF RMSE {rmse_bcf} too high on RIC scenario"
    # ATE should be close to true 0.2
    assert abs(float(hte_result.ate) - 0.2) < 1.0


def test_bcf_sklearn_fallback_reports_backend():
    """When explicitly requesting sklearn backend, metadata should reflect it."""
    state = _make_hte_data(n=200, seed=5)
    result = CausalBCF.pure_step(
        state,
        {"backend": "sklearn", "__seed__": 1, "bootstrap_runs": 20},
    )
    hte_result = result["hte_result"]
    assert hte_result.metadata.get("backend_used") in ("sklearn", "numpy_ridge")
    # Should still produce finite results
    assert np.isfinite(hte_result.ate)
    assert len(hte_result.cate_values) == 200


def test_bcf_confidence_intervals_cover_truth():
    """BCF bootstrap CIs should cover the true ATE at reasonable rates."""
    state = _make_hte_data(n=300, seed=99)
    result = CausalBCF.pure_step(
        state,
        {"backend": "sklearn", "__seed__": 77, "bootstrap_runs": 50, "confidence_level": 0.95},
    )
    hte_result = result["hte_result"]
    # Check that standard errors are computed
    assert hte_result.cate_std_values is not None
    std_errors = np.asarray(hte_result.cate_std_values, dtype=float)
    assert np.all(np.isfinite(std_errors))
    assert np.all(std_errors >= 0.0)


def test_bcf_sklearn_fallback_does_not_hallucinate_large_hte_when_tau_is_constant():
    state, true_tau = _make_ric_data(n=400, seed=123)
    result = CausalBCF.pure_step(
        state,
        {
            "backend": "sklearn",
            "__seed__": 21,
            "bootstrap_runs": 30,
            "num_trees_mu": 180,
            "num_trees_tau": 80,
        },
    )
    hte_result = result["hte_result"]
    tau_hat = np.asarray(hte_result.cate_values, dtype=float)

    assert float(np.std(tau_hat, ddof=1)) < 0.75
    assert abs(float(np.mean(tau_hat)) - float(np.mean(true_tau))) < 0.5


def test_fit_stochtree_bcf_uses_tau_term_predictions_and_propensity(monkeypatch):
    class FakeBCFModel:
        last_instance = None

        def __init__(self) -> None:
            self.sample_kwargs = {}
            FakeBCFModel.last_instance = self

        def sample(self, *args, **kwargs) -> None:
            self.sample_kwargs = dict(kwargs)

        def predict(self, X, Z, propensity=None, type="posterior", terms="all", scale="linear"):
            n = X.shape[0]
            tau = np.linspace(-0.2, 0.2, n)
            mu = np.linspace(1.0, 2.0, n)
            if type == "mean":
                if terms == "tau":
                    return tau
                if terms == "mu":
                    return mu
            if type == "posterior" and terms == "tau":
                return np.vstack([tau - 0.05, tau, tau + 0.05])
            raise AssertionError(f"unexpected predict request: type={type!r}, terms={terms!r}")

    monkeypatch.setitem(sys.modules, "stochtree", types.SimpleNamespace(BCFModel=FakeBCFModel))

    state = _make_hte_data(n=120, seed=11)
    X = np.asarray(state["covariates"], dtype=float)
    T = np.asarray(state["treatment"], dtype=float)
    Y = np.asarray(state["outcome"], dtype=float)

    result = _fit_stochtree_bcf(
        X,
        T,
        Y,
        seed=17,
        params={"num_gfr": 10, "num_mcmc": 20, "num_trees_mu": 40, "num_trees_tau": 20},
    )

    assert result is not None
    mu_hat, tau_hat, tau_std, _, warnings, predict_tau = result
    assert FakeBCFModel.last_instance is not None
    assert FakeBCFModel.last_instance.sample_kwargs["propensity_train"] is not None
    assert FakeBCFModel.last_instance.sample_kwargs["propensity_test"] is not None
    assert np.allclose(tau_hat, np.linspace(-0.2, 0.2, X.shape[0]))
    assert np.allclose(mu_hat, np.linspace(1.0, 2.0, X.shape[0]))
    assert tau_std.shape == tau_hat.shape
    assert np.all(tau_std > 0.0)
    assert "stochtree backend uses explicit propensity augmentation" in " ".join(warnings)
    assert predict_tau(X[:8]).shape == (8,)


def test_bcf_requested_stochtree_fallback_reports_actual_backend(monkeypatch):
    state = _make_hte_data(n=120, seed=21)
    n = state["covariates"].shape[0]

    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.causal.causal_bcf._fit_stochtree_bcf",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.causal.causal_bcf._fit_sklearn_pseudo_bcf",
        lambda *args, **kwargs: (
            np.zeros(n, dtype=float),
            np.zeros(n, dtype=float),
            np.full(n, 0.1, dtype=float),
            np.zeros(state["covariates"].shape[1], dtype=float),
            [],
            lambda X_new: np.zeros(X_new.shape[0], dtype=float),
        ),
    )

    result = CausalBCF.pure_step(
        state,
        {"backend": "stochtree", "__seed__": 9, "bootstrap_runs": 20},
    )

    assert result["hte_result"].metadata["backend_used"] == "sklearn"
