"""Automatic regime diagnostics for causal estimation.

Detects hard estimation regimes (poor overlap, heavy tails, weak signal)
and recommends whether to return point estimates, partial identification
bounds, or abstain.  Integrates with the existing nuisance diagnostics
from ``tmle_core.ATENuisanceBundle.diagnostics()``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RegimeDiagnostics:
    """Summary of the estimation regime difficulty."""

    overlap_quality: str  # "good" | "moderate" | "poor"
    tail_heaviness: float  # excess kurtosis of importance weights
    signal_strength: float  # partial R² of Y on T | X
    effective_sample_size: float
    clipping_fraction: float
    overlap_ntv: float
    recommendation: str  # "point_estimate" | "bounds" | "abstain"


def diagnose_regime(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    propensity: np.ndarray,
    *,
    ess_threshold: float = 48.0,
    ntv_moderate: float = 0.40,
    ntv_poor: float = 0.70,
    clip_bounds: tuple[float, float] = (0.01, 0.99),
) -> RegimeDiagnostics:
    """Diagnose the estimation regime from data and propensity scores.

    Parameters
    ----------
    X : array (n, p)
        Covariates.
    T : array (n,)
        Binary treatment indicator.
    Y : array (n,)
        Outcome.
    propensity : array (n,)
        Estimated propensity scores P(T=1|X).
    ess_threshold:
        Below this ESS, overlap is considered problematic.
    ntv_moderate, ntv_poor:
        Thresholds for normalized treatment variation.
    clip_bounds:
        Propensity clipping bounds used during estimation.
    """
    e = np.asarray(propensity, dtype=float).ravel()
    T = np.asarray(T, dtype=float).ravel()
    Y = np.asarray(Y, dtype=float).ravel()
    X = np.asarray(X, dtype=float)
    n = e.size

    # --- Overlap metrics ---
    e_clipped = np.clip(e, clip_bounds[0], clip_bounds[1])
    weights = 1.0 / (e_clipped * (1.0 - e_clipped))
    w_sum = float(np.sum(weights))
    ess = w_sum**2 / float(np.sum(weights**2)) if w_sum > 0 else 0.0

    clipping_fraction = float(np.mean((e <= clip_bounds[0]) | (e >= clip_bounds[1])))

    # Normalized treatment variation: mean(|e - 0.5| / 0.5)
    overlap_ntv = float(np.mean(np.abs(e - 0.5) / 0.5))

    if overlap_ntv < ntv_moderate and ess >= ess_threshold:
        overlap_quality = "good"
    elif overlap_ntv < ntv_poor and ess >= ess_threshold * 0.5:
        overlap_quality = "moderate"
    else:
        overlap_quality = "poor"

    # --- Tail heaviness (excess kurtosis of importance weights) ---
    w_centered = weights - np.mean(weights)
    w_var = float(np.var(weights))
    if w_var > 1e-12:
        tail_heaviness = float(np.mean(w_centered**4) / w_var**2 - 3.0)
    else:
        tail_heaviness = 0.0

    # --- Signal strength: partial R² of Y on T given X ---
    # Fit simple OLS: Y ~ X, then Y ~ X + T, compare R²
    if X.shape[0] > X.shape[1] + 2:
        try:
            # Full model: Y ~ [X, T]
            X_full = np.column_stack([X, T])
            X_full = np.column_stack([np.ones(n), X_full])
            X_reduced = np.column_stack([np.ones(n), X])

            # OLS via normal equations (numerically stable for moderate p)
            beta_full = np.linalg.lstsq(X_full, Y, rcond=None)[0]
            beta_red = np.linalg.lstsq(X_reduced, Y, rcond=None)[0]

            ss_res_full = float(np.sum((Y - X_full @ beta_full) ** 2))
            ss_res_red = float(np.sum((Y - X_reduced @ beta_red) ** 2))
            ss_total = float(np.sum((Y - np.mean(Y)) ** 2))

            if ss_total > 1e-12:
                signal_strength = max(0.0, (ss_res_red - ss_res_full) / ss_total)
            else:
                signal_strength = 0.0
        except (np.linalg.LinAlgError, ValueError):
            signal_strength = 0.0
    else:
        signal_strength = 0.0

    # --- Recommendation ---
    if overlap_quality == "poor" or ess < ess_threshold * 0.25:
        recommendation = "bounds"
    elif overlap_quality == "moderate" and signal_strength < 0.01:
        recommendation = "abstain"
    else:
        recommendation = "point_estimate"

    return RegimeDiagnostics(
        overlap_quality=overlap_quality,
        tail_heaviness=tail_heaviness,
        signal_strength=signal_strength,
        effective_sample_size=ess,
        clipping_fraction=clipping_fraction,
        overlap_ntv=overlap_ntv,
        recommendation=recommendation,
    )
