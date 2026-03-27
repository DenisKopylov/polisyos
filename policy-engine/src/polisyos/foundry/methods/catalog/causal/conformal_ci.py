"""Split conformal inference for post-hoc CI calibration.

Provides finite-sample coverage guarantees by recalibrating confidence
intervals using held-out nonconformity scores, regardless of the
underlying estimator's distributional assumptions.

Reference: Vovk, Gammerman, Shafer (2005); Lei et al. (2018).
"""

from __future__ import annotations

import numpy as np


def conformal_calibrate_interval(
    point_estimate: float,
    ci_lower: float,
    ci_upper: float,
    calibration_residuals: np.ndarray,
    alpha: float = 0.05,
) -> tuple[float, float, str]:
    """Recalibrate a CI using split conformal inference.

    Parameters
    ----------
    point_estimate:
        The original point estimate (ATE or CATE).
    ci_lower, ci_upper:
        Original confidence interval bounds from any estimator.
    calibration_residuals:
        Absolute residuals ``|true - predicted|`` on a held-out
        calibration set.  For ATE estimation this is typically
        ``|pseudo_outcome_i - ate_hat|`` on left-out cross-fit folds.
    alpha:
        Miscoverage level (default 0.05 for 95% CI).

    Returns
    -------
    (ci_lower, ci_upper, method_label)
        Recalibrated interval and a label describing the method used.
    """
    residuals = np.asarray(calibration_residuals, dtype=float).ravel()
    residuals = residuals[np.isfinite(residuals)]
    n_cal = residuals.size

    if n_cal < 2:
        return ci_lower, ci_upper, "conformal_passthrough"

    # Conformal quantile: ceil((1-α)(n_cal+1)) / n_cal percentile
    # This provides finite-sample marginal coverage ≥ 1-α.
    q_level = min(1.0, (1.0 - alpha) * (1.0 + 1.0 / n_cal))
    conformal_radius = float(np.quantile(np.abs(residuals), q_level))

    # Take the wider of the original and conformal intervals
    conf_lower = point_estimate - conformal_radius
    conf_upper = point_estimate + conformal_radius

    new_lower = min(ci_lower, conf_lower)
    new_upper = max(ci_upper, conf_upper)

    return new_lower, new_upper, "conformal_calibrated"


def conformal_residuals_from_crossfit(
    pseudo_outcomes: np.ndarray,
    point_estimate: float,
) -> np.ndarray:
    """Compute nonconformity scores from cross-fit pseudo-outcomes.

    This is the natural calibration set for ATE estimation: each
    pseudo-outcome is computed on a held-out fold, so the residual
    ``|ψ_i - θ̂|`` is a valid nonconformity score.

    Parameters
    ----------
    pseudo_outcomes:
        AIPW/TMLE pseudo-outcomes from cross-fitting.
    point_estimate:
        The estimated ATE.

    Returns
    -------
    Absolute residuals suitable for ``conformal_calibrate_interval``.
    """
    psi = np.asarray(pseudo_outcomes, dtype=float).ravel()
    psi = psi[np.isfinite(psi)]
    return np.abs(psi - point_estimate)
