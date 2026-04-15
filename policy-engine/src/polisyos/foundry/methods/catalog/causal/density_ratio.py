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

from dataclasses import dataclass
import math
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

MAX_DISTRIBUTIONAL_OT_BINS = 128
DEFAULT_DISTRIBUTIONAL_QUANTILES = (0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
DEFAULT_DISTRIBUTIONAL_TAIL_PROBS = (0.90, 0.95)


@dataclass(frozen=True)
class ScalarDiscreteMeasure:
    """Represent one finite-support scalar distribution used by transport/density-ratio utilities."""
    bin_edges: np.ndarray
    support: np.ndarray
    probabilities: np.ndarray
    sample_size: int
    total_weight: float
    weighting_mode: str
    mean_value: float
    min_value: float
    max_value: float


@dataclass(frozen=True)
class QuantileShiftResult:
    """Quantile shift result data model."""
    quantiles: np.ndarray
    baseline_values: np.ndarray
    counterfactual_values: np.ndarray
    shifts: np.ndarray


@dataclass(frozen=True)
class TailRiskResult:
    """Tail risk result data model."""
    tail_probs: np.ndarray
    thresholds: np.ndarray
    baseline_exceedance_probs: np.ndarray
    counterfactual_exceedance_probs: np.ndarray
    exceedance_deltas: np.ndarray
    baseline_expected_shortfalls: np.ndarray
    counterfactual_expected_shortfalls: np.ndarray
    expected_shortfall_deltas: np.ndarray


@dataclass(frozen=True)
class ScalarOTDistributionalResult:
    """Scalar OT distributional result data model."""
    baseline_measure: ScalarDiscreteMeasure
    counterfactual_measure: ScalarDiscreteMeasure
    coupling_matrix: np.ndarray
    wasserstein_distance: float
    quantile_shift: QuantileShiftResult
    tail_risk: TailRiskResult
    mass_conservation_error: float
    source_marginal_l1_error: float
    target_marginal_l1_error: float
    support_mismatch_note: str | None
    regularization_strength: float
    sinkhorn_iterations: int
    convergence_delta: float
    weighting_mode: str
    density_ratio_diagnostics: dict[str, Any]


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
# Phase D.1 scalar OT helpers
# ---------------------------------------------------------------------------


def _coerce_1d_finite(values: np.ndarray | list[float], *, field_name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{field_name} must be a 1D finite array")
    if arr.size == 0:
        raise ValueError(f"{field_name} must be non-empty")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{field_name} must contain only finite values")
    return arr


def _coerce_2d_finite(
    values: np.ndarray | list[list[float]] | list[float],
    *,
    field_name: str,
) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 1:
        arr = arr[:, None]
    if arr.ndim != 2:
        raise ValueError(f"{field_name} must be a 2D finite array")
    if arr.size == 0:
        raise ValueError(f"{field_name} must be non-empty")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{field_name} must contain only finite values")
    return arr


def _validate_compute_budget(
    *,
    n_bins: int,
    regularization_strength: float,
    max_iter: int,
) -> None:
    if n_bins < 2:
        raise ValueError("n_bins must be at least 2")
    if n_bins > MAX_DISTRIBUTIONAL_OT_BINS:
        raise ValueError(
            f"n_bins exceeds compute budget ({MAX_DISTRIBUTIONAL_OT_BINS}); raw-data OT is prohibited"
        )
    if regularization_strength <= 0.0:
        raise ValueError("regularization_strength must be strictly positive for Sinkhorn OT")
    if max_iter < 1 or max_iter > 200:
        raise ValueError("max_iter must be within [1, 200]")


def _support_mismatch_note(source_values: np.ndarray, target_values: np.ndarray) -> str | None:
    source_min, source_max = float(np.min(source_values)), float(np.max(source_values))
    target_min, target_max = float(np.min(target_values)), float(np.max(target_values))
    overlap_lo = max(source_min, target_min)
    overlap_hi = min(source_max, target_max)
    if overlap_hi < overlap_lo:
        return "disjoint_support_ranges"
    if source_min > target_min or source_max < target_max:
        return "counterfactual_support_extends_beyond_baseline"
    if target_min > source_min or target_max < source_max:
        return "baseline_support_extends_beyond_counterfactual"
    return None


def _build_common_bin_edges(
    baseline_values: np.ndarray,
    counterfactual_values: np.ndarray,
    *,
    n_bins: int,
) -> np.ndarray:
    lower = float(min(np.min(baseline_values), np.min(counterfactual_values)))
    upper = float(max(np.max(baseline_values), np.max(counterfactual_values)))
    if math.isclose(lower, upper, rel_tol=0.0, abs_tol=1e-12):
        lower -= 0.5
        upper += 0.5
    return np.linspace(lower, upper, n_bins + 1, dtype=float)


def _weighted_histogram(values: np.ndarray, edges: np.ndarray, weights: np.ndarray) -> np.ndarray:
    hist, _ = np.histogram(values, bins=edges, weights=weights)
    hist = np.asarray(hist, dtype=float)
    total = float(np.sum(hist))
    if total <= 0.0:
        raise ValueError("discrete histogram mass must be positive")
    return hist / total


def _discretize_scalar_distribution(
    values: np.ndarray | list[float],
    *,
    bin_edges: np.ndarray,
    sample_weights: np.ndarray | list[float] | None = None,
    weighting_mode: str = "uniform",
) -> ScalarDiscreteMeasure:
    arr = _coerce_1d_finite(values, field_name="values")
    if sample_weights is None:
        weights = np.ones(arr.shape[0], dtype=float)
    else:
        weights = _coerce_1d_finite(sample_weights, field_name="sample_weights")
        if weights.shape[0] != arr.shape[0]:
            raise ValueError("sample_weights must align with values")
        if np.any(weights < 0.0):
            raise ValueError("sample_weights must be non-negative")
        if float(np.sum(weights)) <= 0.0:
            raise ValueError("sample_weights must have positive total mass")

    probabilities = _weighted_histogram(arr, bin_edges, weights)
    support = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    counts, _ = np.histogram(arr, bins=bin_edges)
    return ScalarDiscreteMeasure(
        bin_edges=np.asarray(bin_edges, dtype=float),
        support=support,
        probabilities=probabilities,
        sample_size=int(arr.shape[0]),
        total_weight=float(np.sum(weights)),
        weighting_mode=weighting_mode,
        mean_value=float(np.average(arr, weights=weights)),
        min_value=float(np.min(arr)),
        max_value=float(np.max(arr)),
    )


def compute_sinkhorn_coupling(
    source_support: np.ndarray | list[float],
    source_probabilities: np.ndarray | list[float] | None,
    target_support: np.ndarray | list[float],
    target_probabilities: np.ndarray | list[float] | None,
    *,
    regularization_strength: float = 0.05,
    max_iter: int = 200,
    tolerance: float = 1e-8,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Compute sinkhorn coupling helper."""
    if source_probabilities is None or target_probabilities is None:
        raise ValueError(
            "raw sample-to-sample OT is prohibited; provide normalized discrete measures instead"
        )
    _validate_compute_budget(
        n_bins=max(len(source_support), len(target_support)),
        regularization_strength=regularization_strength,
        max_iter=max_iter,
    )

    source_support_arr = _coerce_1d_finite(source_support, field_name="source_support")
    target_support_arr = _coerce_1d_finite(target_support, field_name="target_support")
    source_prob_arr = _coerce_1d_finite(source_probabilities, field_name="source_probabilities")
    target_prob_arr = _coerce_1d_finite(target_probabilities, field_name="target_probabilities")

    if source_support_arr.shape[0] != source_prob_arr.shape[0]:
        raise ValueError("source_probabilities must align with source_support")
    if target_support_arr.shape[0] != target_prob_arr.shape[0]:
        raise ValueError("target_probabilities must align with target_support")
    if np.any(source_prob_arr < 0.0) or np.any(target_prob_arr < 0.0):
        raise ValueError("discrete OT probabilities must be non-negative")

    source_mass = float(np.sum(source_prob_arr))
    target_mass = float(np.sum(target_prob_arr))
    if source_mass <= 0.0 or target_mass <= 0.0:
        raise ValueError("discrete OT probabilities must have positive mass")
    source_prob_arr = source_prob_arr / source_mass
    target_prob_arr = target_prob_arr / target_mass

    cost = np.abs(source_support_arr[:, None] - target_support_arr[None, :])
    cost_scale = max(float(np.max(cost)), 1.0)
    normalized_cost = cost / cost_scale
    kernel = np.exp(-normalized_cost / regularization_strength)
    kernel = np.clip(kernel, 1e-300, None)

    u = np.ones_like(source_prob_arr)
    v = np.ones_like(target_prob_arr)
    convergence_delta = float("inf")
    iterations = 0
    for step in range(1, max_iter + 1):
        prev_u = u.copy()
        prev_v = v.copy()

        Kv = np.clip(kernel @ v, 1e-300, None)
        u = source_prob_arr / Kv
        KTu = np.clip(kernel.T @ u, 1e-300, None)
        v = target_prob_arr / KTu

        convergence_delta = float(
            max(
                np.max(np.abs(u - prev_u)),
                np.max(np.abs(v - prev_v)),
            )
        )
        iterations = step
        if convergence_delta <= tolerance:
            break

    coupling = (u[:, None] * kernel) * v[None, :]
    total_mass = float(np.sum(coupling))
    if total_mass <= 0.0:
        raise ValueError("Sinkhorn coupling collapsed to zero mass")
    coupling = coupling / total_mass

    row_error = float(np.sum(np.abs(np.sum(coupling, axis=1) - source_prob_arr)))
    col_error = float(np.sum(np.abs(np.sum(coupling, axis=0) - target_prob_arr)))
    diagnostics = {
        "mass_conservation_error": max(row_error, col_error),
        "source_marginal_l1_error": row_error,
        "target_marginal_l1_error": col_error,
        "regularization_strength": float(regularization_strength),
        "sinkhorn_iterations": int(iterations),
        "convergence_delta": float(convergence_delta),
    }
    return coupling, diagnostics


def _quantiles_from_discrete_measure(
    support: np.ndarray,
    probabilities: np.ndarray,
    quantiles: np.ndarray,
) -> np.ndarray:
    cdf = np.cumsum(probabilities)
    indices = np.searchsorted(cdf, quantiles, side="left")
    indices = np.clip(indices, 0, support.shape[0] - 1)
    return support[indices]


def _expected_shortfall(
    support: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
) -> float:
    mask = support >= threshold
    exceedance = float(np.sum(probabilities[mask]))
    if exceedance <= 0.0:
        return float("nan")
    return float(np.sum(support[mask] * probabilities[mask]) / exceedance)


def _quantile_shift_result(
    baseline: ScalarDiscreteMeasure,
    counterfactual: ScalarDiscreteMeasure,
    quantiles: tuple[float, ...],
) -> QuantileShiftResult:
    grid = np.asarray(quantiles, dtype=float)
    baseline_values = _quantiles_from_discrete_measure(
        baseline.support,
        baseline.probabilities,
        grid,
    )
    counterfactual_values = _quantiles_from_discrete_measure(
        counterfactual.support,
        counterfactual.probabilities,
        grid,
    )
    return QuantileShiftResult(
        quantiles=grid,
        baseline_values=baseline_values,
        counterfactual_values=counterfactual_values,
        shifts=counterfactual_values - baseline_values,
    )


def _tail_risk_result(
    baseline: ScalarDiscreteMeasure,
    counterfactual: ScalarDiscreteMeasure,
    tail_probs: tuple[float, ...],
) -> TailRiskResult:
    probs = np.asarray(tail_probs, dtype=float)
    thresholds = _quantiles_from_discrete_measure(
        baseline.support,
        baseline.probabilities,
        probs,
    )
    baseline_exceedance = np.asarray(
        [float(np.sum(baseline.probabilities[baseline.support >= threshold])) for threshold in thresholds],
        dtype=float,
    )
    counterfactual_exceedance = np.asarray(
        [float(np.sum(counterfactual.probabilities[counterfactual.support >= threshold])) for threshold in thresholds],
        dtype=float,
    )
    baseline_shortfall = np.asarray(
        [_expected_shortfall(baseline.support, baseline.probabilities, threshold) for threshold in thresholds],
        dtype=float,
    )
    counterfactual_shortfall = np.asarray(
        [
            _expected_shortfall(counterfactual.support, counterfactual.probabilities, threshold)
            for threshold in thresholds
        ],
        dtype=float,
    )
    return TailRiskResult(
        tail_probs=probs,
        thresholds=thresholds,
        baseline_exceedance_probs=baseline_exceedance,
        counterfactual_exceedance_probs=counterfactual_exceedance,
        exceedance_deltas=counterfactual_exceedance - baseline_exceedance,
        baseline_expected_shortfalls=baseline_shortfall,
        counterfactual_expected_shortfalls=counterfactual_shortfall,
        expected_shortfall_deltas=counterfactual_shortfall - baseline_shortfall,
    )


def compute_scalar_distributional_effect(
    baseline_values: np.ndarray | list[float],
    counterfactual_values: np.ndarray | list[float],
    *,
    baseline_covariates: np.ndarray | list[list[float]] | list[float] | None = None,
    counterfactual_covariates: np.ndarray | list[list[float]] | list[float] | None = None,
    density_ratio_method: str = "logistic_trick",
    n_bins: int = 64,
    regularization_strength: float = 0.05,
    max_iter: int = 200,
    quantiles: tuple[float, ...] = DEFAULT_DISTRIBUTIONAL_QUANTILES,
    tail_probs: tuple[float, ...] = DEFAULT_DISTRIBUTIONAL_TAIL_PROBS,
) -> ScalarOTDistributionalResult:
    """Compute scalar distributional effect helper."""
    baseline_arr = _coerce_1d_finite(baseline_values, field_name="baseline_values")
    counterfactual_arr = _coerce_1d_finite(counterfactual_values, field_name="counterfactual_values")
    _validate_compute_budget(
        n_bins=n_bins,
        regularization_strength=regularization_strength,
        max_iter=max_iter,
    )

    weighting_mode = "uniform"
    density_ratio_diagnostics: dict[str, Any] = {}
    baseline_weights: np.ndarray | None = None
    if baseline_covariates is not None and counterfactual_covariates is not None:
        X_source = _coerce_2d_finite(baseline_covariates, field_name="baseline_covariates")
        X_target = _coerce_2d_finite(counterfactual_covariates, field_name="counterfactual_covariates")
        if X_source.shape[0] != baseline_arr.shape[0]:
            raise ValueError("baseline_covariates must align with baseline_values")
        if X_target.shape[0] != counterfactual_arr.shape[0]:
            raise ValueError("counterfactual_covariates must align with counterfactual_values")
        density_ratio_output = DensityRatioEstimator.pure_step(
            {"X_source": X_source, "X_target": X_target},
            {"method": density_ratio_method},
        )
        baseline_weights = np.asarray(density_ratio_output["weights"], dtype=float)
        density_ratio_diagnostics = dict(density_ratio_output["diagnostics"])
        weighting_mode = "density_ratio"

    edges = _build_common_bin_edges(baseline_arr, counterfactual_arr, n_bins=n_bins)
    baseline_measure = _discretize_scalar_distribution(
        baseline_arr,
        bin_edges=edges,
        sample_weights=baseline_weights,
        weighting_mode=weighting_mode,
    )
    counterfactual_measure = _discretize_scalar_distribution(
        counterfactual_arr,
        bin_edges=edges,
        weighting_mode="uniform",
    )

    coupling, diagnostics = compute_sinkhorn_coupling(
        baseline_measure.support,
        baseline_measure.probabilities,
        counterfactual_measure.support,
        counterfactual_measure.probabilities,
        regularization_strength=regularization_strength,
        max_iter=max_iter,
    )
    quantile_shift = _quantile_shift_result(baseline_measure, counterfactual_measure, quantiles)
    tail_risk = _tail_risk_result(baseline_measure, counterfactual_measure, tail_probs)
    cost = np.abs(baseline_measure.support[:, None] - counterfactual_measure.support[None, :])
    wasserstein_distance = float(np.sum(coupling * cost))

    return ScalarOTDistributionalResult(
        baseline_measure=baseline_measure,
        counterfactual_measure=counterfactual_measure,
        coupling_matrix=coupling,
        wasserstein_distance=wasserstein_distance,
        quantile_shift=quantile_shift,
        tail_risk=tail_risk,
        mass_conservation_error=float(diagnostics["mass_conservation_error"]),
        source_marginal_l1_error=float(diagnostics["source_marginal_l1_error"]),
        target_marginal_l1_error=float(diagnostics["target_marginal_l1_error"]),
        support_mismatch_note=_support_mismatch_note(baseline_arr, counterfactual_arr),
        regularization_strength=float(diagnostics["regularization_strength"]),
        sinkhorn_iterations=int(diagnostics["sinkhorn_iterations"]),
        convergence_delta=float(diagnostics["convergence_delta"]),
        weighting_mode=weighting_mode,
        density_ratio_diagnostics=density_ratio_diagnostics,
    )


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
        namespace="",
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


__all__ = [
    "DEFAULT_DISTRIBUTIONAL_QUANTILES",
    "DEFAULT_DISTRIBUTIONAL_TAIL_PROBS",
    "MAX_DISTRIBUTIONAL_OT_BINS",
    "DensityRatioEstimator",
    "QuantileShiftResult",
    "ScalarDiscreteMeasure",
    "ScalarOTDistributionalResult",
    "TailRiskResult",
    "compute_scalar_distributional_effect",
    "compute_sinkhorn_coupling",
]
