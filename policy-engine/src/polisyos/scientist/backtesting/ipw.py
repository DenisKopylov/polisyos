"""Inverse probability weighting corrections for backtest bias."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class IPWResult:
    """Result of inverse probability weighting correction."""

    raw_estimate: float
    ipw_estimate: float
    effective_sample_size: float
    max_weight: float
    weight_variance: float


def compute_propensity_weights(
    treatment: list[int] | np.ndarray,
    covariates: np.ndarray,
    *,
    clip_min: float = 0.01,
    clip_max: float = 0.99,
) -> np.ndarray:
    """Estimate propensity scores via logistic regression (scipy) or fallback.

    Parameters
    ----------
    treatment:
        Binary treatment indicator (0/1).
    covariates:
        2D array of covariates (n_samples, n_features).
    clip_min/clip_max:
        Propensity score clipping bounds to avoid extreme weights.
    """
    t = np.asarray(treatment, dtype=float).ravel()
    X = np.asarray(covariates, dtype=float)

    if X.ndim == 1:
        X = X.reshape(-1, 1)

    # Simple logistic via scipy or fallback to prevalence
    try:
        from scipy.special import expit
        from scipy.optimize import minimize

        def neg_log_lik(beta):
            z = X @ beta[1:] + beta[0]
            p = expit(z)
            p = np.clip(p, 1e-10, 1 - 1e-10)
            return -np.sum(t * np.log(p) + (1 - t) * np.log(1 - p))

        beta0 = np.zeros(X.shape[1] + 1)
        result = minimize(neg_log_lik, beta0, method="BFGS")
        z = X @ result.x[1:] + result.x[0]
        scores = expit(z)
    except ImportError:
        # Fallback: constant propensity = prevalence
        scores = np.full(len(t), np.mean(t))

    return np.clip(scores, clip_min, clip_max)


def ipw_estimate(
    outcomes: list[float] | np.ndarray,
    treatment: list[int] | np.ndarray,
    propensity_scores: np.ndarray,
) -> IPWResult:
    """Compute IPW-adjusted treatment effect estimate.

    Parameters
    ----------
    outcomes:
        Observed outcome values.
    treatment:
        Binary treatment indicator.
    propensity_scores:
        Estimated P(T=1|X) for each unit.
    """
    y = np.asarray(outcomes, dtype=float)
    t = np.asarray(treatment, dtype=float).ravel()
    ps = np.asarray(propensity_scores, dtype=float)

    # Raw ATE
    treated_mask = t == 1
    control_mask = t == 0
    raw_treated = float(np.mean(y[treated_mask])) if np.any(treated_mask) else 0.0
    raw_control = float(np.mean(y[control_mask])) if np.any(control_mask) else 0.0
    raw_estimate = raw_treated - raw_control

    # IPW weights
    weights = np.where(t == 1, 1.0 / ps, 1.0 / (1.0 - ps))

    # Horvitz-Thompson estimator
    ipw_treated = float(np.sum(t * y * weights)) / max(float(np.sum(t * weights)), 1e-10)
    ipw_control = float(np.sum((1 - t) * y * weights)) / max(float(np.sum((1 - t) * weights)), 1e-10)
    ipw_est = ipw_treated - ipw_control

    # Diagnostics
    ess = float(np.sum(weights) ** 2 / np.sum(weights ** 2))

    return IPWResult(
        raw_estimate=raw_estimate,
        ipw_estimate=ipw_est,
        effective_sample_size=ess,
        max_weight=float(np.max(weights)),
        weight_variance=float(np.var(weights)),
    )
