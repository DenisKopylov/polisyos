"""density_ratio — density-ratio estimation for transport reweighting.

Computes importance weights w(x) = p_target(x) / p_source(x) that reweight
source-domain samples to match the target distribution, enabling Bareinboim-Pearl
transportability and covariate-shift correction.

Three methods are provided:

* **logistic_trick** (default, Sugiyama et al. 2012): train a logistic classifier
  to distinguish source from target; w(x) = P(target|x) / P(source|x).
* **kliep** (KL-Importance Estimation Procedure, Sugiyama et al. 2008): direct
  density-ratio estimation minimising KL(target ‖ source).
* **rulsif** (Relative Unconstrained Least-Squares Importance Fitting,
  Yamada et al. 2013): relative density ratio (1-α)p_target + α·p_source.

Output:
    weights       — importance weights for source samples, shape (n_source,)
    diagnostics   — ESS, KL estimate, support mismatch fraction
"""

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


# ---------------------------------------------------------------------------
# Private estimation backends
# ---------------------------------------------------------------------------


def _logistic_trick(
    X_source: np.ndarray,
    X_target: np.ndarray,
    max_iter: int = 100,
    clip_min: float = 1e-4,
) -> np.ndarray:
    """Logistic-trick density ratio estimation.

    Pool source (label=0) and target (label=1), fit logistic regression,
    then w(x) = P(target|x) / P(source|x) = p / (1-p).
    """
    n_s = X_source.shape[0]
    n_t = X_target.shape[0]
    X_pool = np.vstack([X_source, X_target])
    y_pool = np.concatenate([np.zeros(n_s), np.ones(n_t)])

    n = X_pool.shape[0]
    X_aug = np.column_stack([np.ones(n), X_pool])
    beta = np.zeros(X_aug.shape[1])

    for _ in range(max_iter):
        eta = np.clip(X_aug @ beta, -20, 20)
        p = 1.0 / (1.0 + np.exp(-eta))
        W = np.maximum(p * (1 - p), 1e-12)
        grad = X_aug.T @ (y_pool - p)
        H = X_aug.T @ (W[:, None] * X_aug)
        try:
            delta = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            break
        beta += delta
        if np.max(np.abs(delta)) < 1e-8:
            break

    # Predict on source samples
    X_src_aug = np.column_stack([np.ones(n_s), X_source])
    eta_s = np.clip(X_src_aug @ beta, -20, 20)
    p_s = 1.0 / (1.0 + np.exp(-eta_s))
    p_s = np.clip(p_s, clip_min, 1.0 - clip_min)

    # Adjust for class imbalance: multiply by n_s/n_t
    raw_ratio = p_s / (1.0 - p_s)
    balance_factor = n_s / max(n_t, 1)
    weights = raw_ratio * balance_factor

    # Normalise so weights sum to n_source
    weights = weights * n_s / max(np.sum(weights), 1e-12)
    return weights.astype(float)


def _kliep(
    X_source: np.ndarray,
    X_target: np.ndarray,
    n_kernels: int = 100,
    sigma: float | None = None,
    max_iter: int = 1000,
    lr: float = 1e-3,
) -> np.ndarray:
    """KL-Importance Estimation Procedure (KLIEP).

    Density ratio modelled as w(x) = Σ_l α_l * φ_l(x) with RBF kernels
    centred at target samples (subsampled to n_kernels).
    Objective: maximise E_target[log w(x)] subject to E_source[w(x)] = 1.
    """
    n_s = X_source.shape[0]
    n_t = X_target.shape[0]

    # Kernel centres: subsample target
    rng = np.random.default_rng(0)
    idx = rng.choice(n_t, size=min(n_kernels, n_t), replace=False)
    centres = X_target[idx]

    # Bandwidth: median heuristic if not supplied
    if sigma is None:
        dists = np.sqrt(((X_source[:, None, :] - centres[None, :, :]) ** 2).sum(-1))
        sigma = float(np.median(dists)) + 1e-6

    def rbf(X: np.ndarray) -> np.ndarray:
        d = ((X[:, None, :] - centres[None, :, :]) ** 2).sum(-1)
        return np.exp(-d / (2 * sigma ** 2))

    Phi_s = rbf(X_source)   # (n_s, n_kernels)
    Phi_t = rbf(X_target)   # (n_t, n_kernels)

    alpha = np.ones(len(centres)) / len(centres)

    for _ in range(max_iter):
        w_s = np.clip(Phi_s @ alpha, 1e-8, None)
        w_t = np.clip(Phi_t @ alpha, 1e-8, None)

        # Gradient: ∂/∂α [mean_t log w_t] s.t. mean_s w_s = 1
        # Projected gradient: grad - (grad · constraint_gradient) * constraint_gradient
        grad = np.mean(Phi_t / w_t[:, None], axis=0)
        constraint_grad = np.mean(Phi_s, axis=0)
        lam = np.dot(grad, constraint_grad) / max(np.dot(constraint_grad, constraint_grad), 1e-12)
        alpha += lr * (grad - lam * constraint_grad)
        alpha = np.maximum(alpha, 0)

        # Renormalise
        c = np.dot(np.mean(Phi_s, axis=0), alpha)
        if c > 1e-12:
            alpha /= c

    weights = np.clip(Phi_s @ alpha, 0, None)
    weights = weights * n_s / max(np.sum(weights), 1e-12)
    return weights.astype(float)


def _rulsif(
    X_source: np.ndarray,
    X_target: np.ndarray,
    alpha: float = 0.1,
    n_kernels: int = 100,
    sigma: float | None = None,
    lam: float = 1e-3,
) -> np.ndarray:
    """Relative ULSif (RuLSIF) density ratio estimation.

    Estimates the relative density ratio r_α(x) = p_target / ((1-α)p_target + α·p_source).
    Uses kernel regression with closed-form solution.
    """
    n_s = X_source.shape[0]
    n_t = X_target.shape[0]

    rng = np.random.default_rng(0)
    idx_s = rng.choice(n_s, size=min(n_kernels, n_s), replace=False)
    idx_t = rng.choice(n_t, size=min(n_kernels, n_t), replace=False)
    centres = np.vstack([X_source[idx_s], X_target[idx_t]])

    if sigma is None:
        dists = np.sqrt(((X_source[:, None, :] - centres[None, :, :]) ** 2).sum(-1))
        sigma = float(np.median(dists)) + 1e-6

    def rbf(X: np.ndarray) -> np.ndarray:
        d = ((X[:, None, :] - centres[None, :, :]) ** 2).sum(-1)
        return np.exp(-d / (2 * sigma ** 2))

    Phi_s = rbf(X_source)   # (n_s, n_kernels)
    Phi_t = rbf(X_target)   # (n_t, n_kernels)

    # H = (1-α)/n_t * Phi_t^T Phi_t + α/n_s * Phi_s^T Phi_s + λI
    H = (
        (1 - alpha) / n_t * Phi_t.T @ Phi_t
        + alpha / n_s * Phi_s.T @ Phi_s
        + lam * np.eye(len(centres))
    )
    h = np.mean(Phi_t, axis=0)

    try:
        theta = np.linalg.solve(H, h)
    except np.linalg.LinAlgError:
        theta = np.linalg.lstsq(H, h, rcond=None)[0]

    weights = np.clip(Phi_s @ theta, 0, None)
    weights = weights * n_s / max(np.sum(weights), 1e-12)
    return weights.astype(float)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def _compute_diagnostics(
    weights: np.ndarray,
    X_source: np.ndarray,
    X_target: np.ndarray,
) -> dict[str, Any]:
    """Compute weight quality diagnostics."""
    n_s = len(weights)

    # Effective Sample Size
    w_norm = weights / max(np.sum(weights), 1e-12)
    ess = float(1.0 / max(np.sum(w_norm ** 2), 1e-12))
    ess_fraction = ess / n_s

    # Support mismatch: fraction of source samples with extreme weights
    w_median = float(np.median(weights))
    threshold = 5.0 * w_median if w_median > 0 else 5.0
    support_mismatch = float(np.mean(weights > threshold))

    # KL divergence estimate: E_source[w log w] (approximate)
    w_clipped = np.clip(weights, 1e-12, None)
    kl_estimate = float(np.mean(w_clipped * np.log(w_clipped + 1e-12)) - np.mean(np.log(w_clipped + 1e-12)))

    # Covariate balance check (weighted mean difference)
    w_n = weights / max(np.sum(weights), 1e-12)
    weighted_mean_s = X_source.T @ w_n
    mean_t = np.mean(X_target, axis=0)
    balance_rmse = float(np.sqrt(np.mean((weighted_mean_s - mean_t) ** 2)))

    return {
        "effective_sample_size": ess,
        "ess_fraction": ess_fraction,
        "support_mismatch_fraction": support_mismatch,
        "kl_divergence_estimate": kl_estimate,
        "covariate_balance_rmse": balance_rmse,
        "weight_min": float(np.min(weights)),
        "weight_max": float(np.max(weights)),
        "weight_mean": float(np.mean(weights)),
        "weight_std": float(np.std(weights)),
    }


# ---------------------------------------------------------------------------
# Foundry method
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.transport",
    version="1.0.0",
    tags={"causal", "transport", "density-ratio", "covariate-shift", "reweighting"},
)
class DensityRatioEstimator:
    """Density-ratio reweighting for Bareinboim-Pearl transportability.

    Estimates importance weights w(x) = p_target(x) / p_source(x) so that
    source-domain samples reweighted by w can represent the target population.

    Input slots:
        X_source — source-domain covariate matrix  (n_source, n_features)
        X_target — target-domain covariate matrix  (n_target, n_features)

    Output slots:
        weights     — per-sample importance weights  (n_source,)
        diagnostics — ESS, KL estimate, support mismatch, balance RMSE

    Supported methods (param ``method``):
        ``logistic_trick`` — default; very fast; good general-purpose choice
        ``kliep``          — KLIEP with RBF kernels; accurate for smooth densities
        ``rulsif``         — RuLSIF; avoids density-ratio divergence near 0; more stable
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="density_ratio",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "X_source",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_source", "n_features"),
                ),
                SlotSpec(
                    "X_target",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_target", "n_features"),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "weights",
                    SlotType.VECTOR,
                    Unit("importance_weight", "ratio"),
                    shape=("n_source",),
                ),
                SlotSpec("diagnostics", SlotType.SCALAR, Unit("diagnostic", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="method", default="logistic_trick"),
            ParameterSpec(name="n_kernels", default=100),
            ParameterSpec(name="max_iter", default=1000),
            ParameterSpec(name="alpha", default=0.1, bounds=(0.0, 0.5)),  # RuLSIF α
            ParameterSpec(name="lambda_reg", default=1e-3, bounds=(1e-8, 1.0)),
            ParameterSpec(name="clip_min", default=1e-4, bounds=(1e-6, 0.1)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Density-ratio estimation for transport reweighting: estimates "
            "w(x) = p_target(x) / p_source(x) to reweight source samples "
            "so they represent the target population."
        ),
        tags=frozenset(
            {"causal", "transport", "density-ratio", "covariate-shift", "reweighting", "kliep", "rulsif"}
        ),
        citations=(
            "Sugiyama, M. et al. (2012). Density Ratio Estimation in Machine Learning. Cambridge.",
            "Sugiyama, M. et al. (2008). Direct Importance Estimation with Model Selection. ECML.",
            "Yamada, M. et al. (2013). Relative Density-Ratio Estimation. Neural Computation.",
            "Bareinboim, E. & Pearl, J. (2016). Causal Inference and the Data-Fusion Problem. PNAS.",
        ),
        equations={
            "logistic_trick": "w(x) = P(target|x) / P(source|x) · (n_source/n_target)",
            "kliep": "max_α Σ_target log(w_α(x)) s.t. E_source[w_α] = 1",
            "rulsif": "r_α(x) = p_target / ((1-α)p_target + α·p_source)",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Transport formula (TR algorithm) requires density ratio; "
            "covariate shift correction; external validity reweighting."
        ),
        when_not_to_use=(
            "Distributions have non-overlapping support (weights will be extreme); "
            "very high-dimensional X without kernel selection; n_source or n_target < 20."
        ),
        prerequisites=(),
        diagnostic_checks=("causal.diagnostics.positivity_check@1.0.0",),
        typical_min_obs=50,
        output_interpretation=(
            "weights: multiply by source outcomes to get transport-corrected estimates. "
            "ESS fraction > 0.3 indicates adequate effective sample size. "
            "Support mismatch > 0.1 suggests poor overlap and unreliable estimation."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X_source = np.asarray(state["X_source"], dtype=float)
        X_target = np.asarray(state["X_target"], dtype=float)

        if X_source.ndim == 1:
            X_source = X_source[:, None]
        if X_target.ndim == 1:
            X_target = X_target[:, None]

        method = str(params.get("method", "logistic_trick")).lower()
        n_kernels = int(params.get("n_kernels", 100))
        max_iter = int(params.get("max_iter", 1000))
        alpha_rulsif = float(params.get("alpha", 0.1))
        lambda_reg = float(params.get("lambda_reg", 1e-3))
        clip_min = float(params.get("clip_min", 1e-4))

        if method == "logistic_trick":
            weights = _logistic_trick(X_source, X_target, max_iter=max_iter, clip_min=clip_min)
        elif method == "kliep":
            weights = _kliep(X_source, X_target, n_kernels=n_kernels, max_iter=max_iter)
        elif method == "rulsif":
            weights = _rulsif(
                X_source,
                X_target,
                alpha=alpha_rulsif,
                n_kernels=n_kernels,
                lam=lambda_reg,
            )
        else:
            raise ValueError(
                f"Unknown density ratio method '{method}'. "
                "Choose from: 'logistic_trick', 'kliep', 'rulsif'."
            )

        diagnostics = _compute_diagnostics(weights, X_source, X_target)
        diagnostics["method"] = method
        diagnostics["n_source"] = int(X_source.shape[0])
        diagnostics["n_target"] = int(X_target.shape[0])

        return {
            "weights": weights.tolist(),
            "diagnostics": diagnostics,
        }


__all__ = ["DensityRatioEstimator"]
