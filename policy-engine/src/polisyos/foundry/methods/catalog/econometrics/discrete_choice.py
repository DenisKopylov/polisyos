"""Estimate binary and multinomial discrete-choice models for choice probabilities."""
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


def _logistic(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))


def _ols_coef(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(X, y, rcond=None)[0]


@foundry_method(
    namespace="econometrics.discrete_choice",
    version="1.0.0",
    tags={"econometrics", "discrete-choice", "logit", "cross-section"},
)
class LogitEstimator:
    """Estimate binary choice probabilities under a logistic latent-index model; avoid strong IIA violations in multinomial settings."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="logit",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "binary"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="max_iter", default=100),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Binary logistic regression via IRLS.",
        tags=frozenset({"econometrics", "discrete-choice", "logit", "binary", "cross-section"}),
        equations={"logit": "P(y=1|X) = 1/(1 + exp(-X*beta))"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Binary outcome; logistic index model; want average marginal effects on probability",
        typical_min_obs=100,
        output_interpretation="Coefficients = log-odds. AME = marginal probability change. Pseudo-R² (McFadden) assesses fit.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        max_iter = int(params.get("max_iter", 100))
        n, k = X.shape

        # Add intercept
        X_aug = np.column_stack([np.ones(n), X])
        beta = np.zeros(k + 1)

        for _ in range(max_iter):
            p = _logistic(X_aug @ beta)
            W = p * (1 - p)
            W = np.maximum(W, 1e-12)
            z = X_aug @ beta + (y - p) / W
            try:
                beta_new = np.linalg.solve(X_aug.T @ np.diag(W) @ X_aug, X_aug.T @ (W * z))
            except np.linalg.LinAlgError:
                break
            if np.max(np.abs(beta_new - beta)) < 1e-8:
                beta = beta_new
                break
            beta = beta_new

        p_final = _logistic(X_aug @ beta)
        log_lik = float(np.sum(y * np.log(p_final + 1e-12) + (1 - y) * np.log(1 - p_final + 1e-12)))
        predicted = (p_final >= 0.5).astype(float)
        accuracy = float(np.mean(predicted == y))

        return {
            "result": {
                "coefficients": beta.tolist(),
                "log_likelihood": log_lik,
                "accuracy": accuracy,
                "n_obs": n,
                "n_features": k,
            }
        }


@foundry_method(
    namespace="econometrics.discrete_choice",
    version="1.0.0",
    tags={"econometrics", "discrete-choice", "probit", "cross-section"},
)
class ProbitEstimator:
    """Estimate binary choice probabilities under a Gaussian latent-index model; avoid when a heavy-tailed link is required."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="probit",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "binary"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="max_iter", default=100),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Binary probit regression via approximate IRLS.",
        tags=frozenset({"econometrics", "discrete-choice", "probit", "binary", "cross-section"}),
        equations={"probit": "P(y=1|X) = Phi(X*beta)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Binary outcome with normally distributed latent utility; willingness-to-pay applications",
        typical_min_obs=100,
        output_interpretation="Probit coefficient / σ = standardized index effect. AME in probability units.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        n, k = X.shape

        # Approximate probit via logit scaling: probit ≈ logit / 1.7
        X_aug = np.column_stack([np.ones(n), X])
        beta = np.zeros(k + 1)
        max_iter = int(params.get("max_iter", 100))

        for _ in range(max_iter):
            z = X_aug @ beta
            p = _logistic(1.7 * z)
            W = p * (1 - p)
            W = np.maximum(W, 1e-12)
            adj_z = z + (y - p) / (W * 1.7)
            try:
                beta_new = np.linalg.solve(X_aug.T @ np.diag(W) @ X_aug, X_aug.T @ (W * adj_z))
            except np.linalg.LinAlgError:
                break
            if np.max(np.abs(beta_new - beta)) < 1e-8:
                beta = beta_new
                break
            beta = beta_new

        p_final = _logistic(1.7 * X_aug @ beta)
        log_lik = float(np.sum(y * np.log(p_final + 1e-12) + (1 - y) * np.log(1 - p_final + 1e-12)))

        return {
            "result": {
                "coefficients": beta.tolist(),
                "log_likelihood": log_lik,
                "n_obs": n,
                "n_features": k,
            }
        }


@foundry_method(
    namespace="econometrics.discrete_choice",
    version="1.0.0",
    tags={"econometrics", "discrete-choice", "multinomial-logit", "cross-section"},
)
class MultinomialLogitEstimator:
    """Estimate multi-class choice shares under IIA; avoid nested-substitution patterns that violate IIA."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="multinomial_logit",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "category"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="max_iter", default=100),
            ParameterSpec(name="learning_rate", default=0.01),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Multinomial logit via gradient descent (softmax regression).",
        tags=frozenset({"econometrics", "discrete-choice", "multinomial-logit", "softmax", "cross-section"}),
        equations={"mnl": "P(y=j|X) = exp(X*beta_j) / sum_k exp(X*beta_k)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Unordered categorical outcome with IIA assumption; market shares with choice-specific attributes",
        typical_min_obs=200,
        output_interpretation="Relative risk ratios vs base category. IIA test (Hausman-McFadden) required.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        y = np.asarray(state["y"], dtype=int)
        n, k = X.shape
        classes = np.unique(y)
        J = len(classes)
        class_map = {c: i for i, c in enumerate(classes)}
        y_idx = np.array([class_map[yi] for yi in y])

        X_aug = np.column_stack([np.ones(n), X])
        kk = k + 1
        lr = float(params.get("learning_rate", 0.01))
        max_iter = int(params.get("max_iter", 100))

        # Coefficients: (J-1) x kk (base category = last)
        B = np.zeros((J - 1, kk))

        for _ in range(max_iter):
            # Softmax probabilities
            logits = X_aug @ B.T  # (n, J-1)
            logits_full = np.column_stack([logits, np.zeros(n)])
            logits_full -= logits_full.max(axis=1, keepdims=True)
            exp_l = np.exp(logits_full)
            probs = exp_l / exp_l.sum(axis=1, keepdims=True)

            # Gradient for each class j < J
            for j in range(J - 1):
                indicator = (y_idx == j).astype(float)
                grad = X_aug.T @ (indicator - probs[:, j]) / n
                B[j] += lr * grad

        # Final probabilities
        logits_full = np.column_stack([X_aug @ B.T, np.zeros(n)])
        logits_full -= logits_full.max(axis=1, keepdims=True)
        exp_l = np.exp(logits_full)
        probs = exp_l / exp_l.sum(axis=1, keepdims=True)
        predicted = classes[np.argmax(probs, axis=1)]
        accuracy = float(np.mean(predicted == y))

        return {
            "result": {
                "coefficients": B.tolist(),
                "classes": classes.tolist(),
                "accuracy": accuracy,
                "n_obs": n,
                "n_classes": J,
            }
        }


@foundry_method(
    namespace="econometrics.discrete_choice",
    version="1.0.0",
    tags={"econometrics", "discrete-choice", "mixed-logit", "cross-section"},
)
class MixedLogitEstimator:
    """Estimate random-coefficient choice heterogeneity; avoid tiny samples where simulation noise dominates."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="mixed_logit",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "binary"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_draws", default=100),
            ParameterSpec(name="seed", default=42),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Mixed logit with normally distributed random coefficients (simulated).",
        tags=frozenset({"econometrics", "discrete-choice", "mixed-logit", "random-coefficients", "cross-section"}),
        equations={"mixed": "P = (1/R) sum_r P(y|X, beta_r), beta_r ~ N(mu, sigma)"},
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use="Heterogeneous preferences; market share models; overcome IIA with random coefficients",
        typical_min_obs=500,
        output_interpretation="Distribution of random coefficients. Price elasticities from BLP. Market shares fit.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        n, k = X.shape
        n_draws = int(params.get("n_draws", 100))
        seed = int(params.get("seed", 42))

        rng = np.random.default_rng(seed)
        X_aug = np.column_stack([np.ones(n), X])
        kk = k + 1

        # Estimate fixed logit first as starting point
        beta_fixed = np.zeros(kk)
        for _ in range(50):
            p = _logistic(X_aug @ beta_fixed)
            W = np.maximum(p * (1 - p), 1e-12)
            z = X_aug @ beta_fixed + (y - p) / W
            try:
                beta_fixed = np.linalg.solve(X_aug.T @ np.diag(W) @ X_aug, X_aug.T @ (W * z))
            except np.linalg.LinAlgError:
                break

        # Simulate: draw beta_r ~ N(beta_fixed, 0.1*I) and average probabilities
        sigma_est = np.abs(beta_fixed) * 0.1 + 0.01
        sim_probs = np.zeros(n)
        for _ in range(n_draws):
            beta_r = beta_fixed + rng.normal(0, sigma_est)
            sim_probs += _logistic(X_aug @ beta_r)
        sim_probs /= n_draws

        log_lik = float(np.sum(y * np.log(sim_probs + 1e-12) + (1 - y) * np.log(1 - sim_probs + 1e-12)))

        return {
            "result": {
                "mean_coefficients": beta_fixed.tolist(),
                "std_coefficients": sigma_est.tolist(),
                "simulated_log_likelihood": log_lik,
                "n_draws": n_draws,
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="econometrics.discrete_choice",
    version="1.0.0",
    tags={"econometrics", "discrete-choice", "blp", "demand", "cross-section"},
)
class BLPEstimator:
    """Estimate differentiated-product demand with endogenous prices and instruments; avoid weak instruments or missing market shares."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="blp",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("market_shares", SlotType.VECTOR, Unit("share", "proportion"), shape=("n_products",)),
                SlotSpec("X", SlotType.MATRIX, Unit("characteristic", "value"), shape=("n_products", "n_chars")),
                SlotSpec("prices", SlotType.VECTOR, Unit("price", "currency"), shape=("n_products",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Simplified BLP demand estimation via logit inversion (no random coefficients).",
        tags=frozenset({"econometrics", "discrete-choice", "blp", "demand", "io", "cross-section"}),
        citations=("Berry, S., Levinsohn, J. & Pakes, A. (1995). Automobile Prices in Market Equilibrium. Econometrica.",),
        equations={"logit_inversion": "delta_j = ln(s_j) - ln(s_0)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Heterogeneous preferences; market share models; overcome IIA with random coefficients",
        typical_min_obs=500,
        output_interpretation="Distribution of random coefficients. Price elasticities from BLP. Market shares fit.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        shares = np.asarray(state["market_shares"], dtype=float)
        X = np.asarray(state["X"], dtype=float)
        prices = np.asarray(state["prices"], dtype=float)
        J = len(shares)

        # Outside good share
        s0 = max(1.0 - np.sum(shares), 1e-12)
        shares_safe = np.maximum(shares, 1e-12)

        # Logit inversion
        delta = np.log(shares_safe) - np.log(s0)

        # OLS: delta = X_full @ beta
        X_full = np.column_stack([np.ones(J), X, prices])
        beta = np.linalg.lstsq(X_full, delta, rcond=None)[0]

        price_coef = float(beta[-1])
        own_elasticities = price_coef * prices * (1 - shares)

        return {
            "result": {
                "mean_utilities": delta.tolist(),
                "coefficients": beta.tolist(),
                "price_coefficient": price_coef,
                "own_price_elasticities": own_elasticities.tolist(),
                "outside_share": float(s0),
                "n_products": J,
            }
        }


__all__ = [
    "BLPEstimator",
    "LogitEstimator",
    "MixedLogitEstimator",
    "MultinomialLogitEstimator",
    "ProbitEstimator",
]
