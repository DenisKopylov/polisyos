"""Public uncertainty sensitivity module API."""
from __future__ import annotations

import numpy as np


def compute_first_order_indices(
    input_samples: dict[str, np.ndarray],
    outputs: np.ndarray,
    input_names: list[str],
) -> dict[str, float]:
    """Regression-based first-order sensitivity indices.

    Fits an OLS linear model ``Y = X @ beta + eps`` and computes
    ``S_i = (beta_i * std(X_i))^2 / var(Y)`` for each input.

    For a truly linear model with independent inputs the indices
    sum to approximately 1.0.  For nonlinear models, the residual
    captures interaction and higher-order effects.
    """
    if len(input_names) < 2:
        raise ValueError("Need at least 2 inputs for sensitivity analysis")

    n = len(outputs)
    if n < len(input_names) + 1:
        raise ValueError("Too few samples for regression-based sensitivity")

    var_y = float(np.var(outputs, ddof=1))
    if var_y < 1e-30:
        return {name: 0.0 for name in input_names}

    # Build design matrix (no intercept — centred data)
    X = np.column_stack([input_samples[name] for name in input_names])
    X_centered = X - X.mean(axis=0)
    y_centered = outputs - outputs.mean()

    # OLS via lstsq
    beta, _, _, _ = np.linalg.lstsq(X_centered, y_centered, rcond=None)

    stds = np.std(X, axis=0, ddof=1)
    raw_indices = {
        name: float((beta[i] * stds[i]) ** 2 / var_y)
        for i, name in enumerate(input_names)
    }

    return raw_indices
