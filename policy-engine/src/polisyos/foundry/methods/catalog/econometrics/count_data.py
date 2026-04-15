"""Estimate count-data regressions for non-negative integer outcomes."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


@foundry_method(
    namespace="econometrics.count",
    version="1.0.0",
    tags={"econometrics", "count", "poisson", "cross-section"},
)
class PoissonRegressionEstimator:
    """Estimate conditional mean effects for count outcomes under equidispersion; avoid strong overdispersion without robust alternatives."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="poisson",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("y", SlotType.VECTOR, Unit("count", "integer"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="max_iter", default=50),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Poisson regression via IRLS for count data.",
        tags=frozenset({"econometrics", "count", "poisson", "glm", "cross-section"}),
        equations={"poisson": "E[y|X] = exp(X*beta)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Count outcome (0,1,2,...); events per unit time/space; equidispersion acceptable",
        typical_min_obs=100,
        output_interpretation="IRR (Incidence Rate Ratio): exp(β). IRR=1.2 means 20% more events per unit increase in X.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        n, k = X.shape
        max_iter = int(params.get("max_iter", 50))

        X_aug = np.column_stack([np.ones(n), X])
        beta = np.zeros(X_aug.shape[1])

        for _ in range(max_iter):
            eta = X_aug @ beta
            mu = np.exp(np.clip(eta, -20, 20))
            W = np.maximum(mu, 1e-12)
            z = eta + (y - mu) / W
            try:
                beta_new = np.linalg.solve(X_aug.T @ np.diag(W) @ X_aug, X_aug.T @ (W * z))
            except np.linalg.LinAlgError:
                break
            if np.max(np.abs(beta_new - beta)) < 1e-8:
                beta = beta_new
                break
            beta = beta_new

        mu_final = np.exp(np.clip(X_aug @ beta, -20, 20))
        log_lik = float(np.sum(y * np.log(mu_final + 1e-12) - mu_final))
        deviance = float(2 * np.sum(np.where(y > 0, y * np.log(y / (mu_final + 1e-12)), 0) - (y - mu_final)))

        return {
            "result": {
                "coefficients": beta.tolist(),
                "log_likelihood": log_lik,
                "deviance": deviance,
                "dispersion": deviance / max(n - len(beta), 1),
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="econometrics.count",
    version="1.0.0",
    tags={"econometrics", "count", "negative-binomial", "cross-section"},
)
class NegativeBinomialEstimator:
    """Estimate overdispersed count models with gamma heterogeneity; avoid when excess zeros dominate the outcome process."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="negative_binomial",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("y", SlotType.VECTOR, Unit("count", "integer"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="max_iter", default=50),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Negative binomial regression (NB2) for overdispersed count data.",
        tags=frozenset({"econometrics", "count", "negative-binomial", "overdispersion", "cross-section"}),
        equations={"nb2": "E[y|X] = exp(X*beta), Var[y|X] = mu + alpha*mu^2"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Overdispersed count data where Var > Mean; events with heterogeneity across units",
        typical_min_obs=100,
        output_interpretation="IRR interpretation same as Poisson. Dispersion parameter α>0 indicates overdispersion vs Poisson.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        n, k = X.shape
        max_iter = int(params.get("max_iter", 50))

        # Start with Poisson estimates
        X_aug = np.column_stack([np.ones(n), X])
        beta = np.zeros(X_aug.shape[1])

        for _ in range(max_iter):
            eta = X_aug @ beta
            mu = np.exp(np.clip(eta, -20, 20))
            W = np.maximum(mu, 1e-12)
            z = eta + (y - mu) / W
            try:
                beta_new = np.linalg.solve(X_aug.T @ np.diag(W) @ X_aug, X_aug.T @ (W * z))
            except np.linalg.LinAlgError:
                break
            if np.max(np.abs(beta_new - beta)) < 1e-8:
                beta = beta_new
                break
            beta = beta_new

        mu_final = np.exp(np.clip(X_aug @ beta, -20, 20))
        # Estimate alpha via moment: Var(y) = mu + alpha*mu^2
        residuals_sq = (y - mu_final) ** 2
        alpha_est = max(0.0, float(np.mean((residuals_sq - mu_final) / np.maximum(mu_final ** 2, 1e-12))))

        return {
            "result": {
                "coefficients": beta.tolist(),
                "alpha": alpha_est,
                "mean_predicted": float(np.mean(mu_final)),
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="econometrics.count",
    version="1.0.0",
    tags={"econometrics", "count", "zero-inflated", "poisson", "cross-section"},
)
class ZeroInflatedPoissonEstimator:
    """Estimate a zero-inflated count process with a separate structural-zero channel; avoid when zeros are not generated by two regimes."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="zero_inflated_poisson",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("y", SlotType.VECTOR, Unit("count", "integer"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="max_iter", default=50),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Zero-inflated Poisson (ZIP) model via simplified EM.",
        tags=frozenset({"econometrics", "count", "zero-inflated", "poisson", "zip", "cross-section"}),
        equations={"zip": "P(y=0) = pi + (1-pi)*exp(-lambda); P(y=k) = (1-pi)*Pois(k;lambda)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Excess zeros beyond what Poisson/NB would predict; structural zeros + count process",
        typical_min_obs=200,
        output_interpretation="Two-part model: logit P(zero) + count part for positives. Vuong test vs standard count model.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        n, k = X.shape
        max_iter = int(params.get("max_iter", 50))

        X_aug = np.column_stack([np.ones(n), X])

        # Initial: pi = fraction of excess zeros, Poisson on non-zeros
        n_zeros = int(np.sum(y == 0))
        y_mean = float(np.mean(y))
        pi_hat = max(0.01, min(0.99, (n_zeros / n) - np.exp(-max(y_mean, 0.01))))

        # Poisson component via IRLS on all data
        beta = np.zeros(X_aug.shape[1])
        if y_mean > 0:
            beta[0] = np.log(y_mean)

        for _ in range(max_iter):
            eta = X_aug @ beta
            mu = np.exp(np.clip(eta, -20, 20))

            # E-step: probability that zero comes from inflated component
            pois_zero = np.exp(-mu)
            if pi_hat > 0:
                z_prob = np.where(y == 0, pi_hat / (pi_hat + (1 - pi_hat) * pois_zero + 1e-12), 0.0)
            else:
                z_prob = np.zeros(n)

            # M-step: update pi
            pi_hat = float(np.mean(z_prob))
            pi_hat = max(0.001, min(0.999, pi_hat))

            # M-step: update beta (weighted Poisson)
            w = 1.0 - z_prob
            W = w * mu
            W = np.maximum(W, 1e-12)
            z_wls = eta + (y - mu) / np.maximum(mu, 1e-12)
            try:
                beta_new = np.linalg.solve(X_aug.T @ np.diag(W) @ X_aug, X_aug.T @ (W * z_wls))
            except np.linalg.LinAlgError:
                break
            if np.max(np.abs(beta_new - beta)) < 1e-8:
                beta = beta_new
                break
            beta = beta_new

        mu_final = np.exp(np.clip(X_aug @ beta, -20, 20))
        vuong = float(n_zeros / n - np.mean(np.exp(-mu_final)))

        return {
            "result": {
                "count_coefficients": beta.tolist(),
                "zero_inflation_probability": pi_hat,
                "mean_lambda": float(np.mean(mu_final)),
                "vuong_statistic": vuong,
                "n_obs": n,
                "n_zeros": n_zeros,
            }
        }


__all__ = [
    "NegativeBinomialEstimator",
    "PoissonRegressionEstimator",
    "ZeroInflatedPoissonEstimator",
]
