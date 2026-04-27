"""Small deterministic linear algebra helpers for model-agnostic adapters."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def fit_weighted_ridge(
    *,
    feature_names: Sequence[str],
    rows: Sequence[Mapping[str, float]],
    targets: Sequence[float],
    weights: Sequence[float],
    alpha: float,
) -> tuple[dict[str, float], dict[str, float]]:
    """Fit a no-intercept weighted ridge model and return coefficients and SEs."""

    if len(rows) != len(targets) or len(rows) != len(weights):
        raise ValueError("rows, targets, and weights must have equal length")
    if not rows:
        raise ValueError("at least one regression row is required")
    if alpha < 0.0:
        raise ValueError("alpha must be non-negative")
    p = len(feature_names)
    xtwx = [[0.0 for _ in range(p)] for _ in range(p)]
    xtwy = [0.0 for _ in range(p)]
    for row, target, weight in zip(rows, targets, weights, strict=True):
        if weight < 0.0:
            raise ValueError("weights must be non-negative")
        y = _finite(target, name="target")
        values = [_finite(row.get(feature, 0.0), name=feature) for feature in feature_names]
        for i, left in enumerate(values):
            xtwy[i] += weight * left * y
            for j, right in enumerate(values):
                xtwx[i][j] += weight * left * right
    for i in range(p):
        xtwx[i][i] += alpha

    coefs = _solve_with_jitter(xtwx, xtwy)
    fitted = [
        sum(
            coef * float(row.get(feature, 0.0))
            for coef, feature in zip(coefs, feature_names, strict=True)
        )
        for row in rows
    ]
    effective_df = max(1, len(rows) - p)
    rss = sum(
        weight * (target - fitted_value) ** 2
        for target, fitted_value, weight in zip(targets, fitted, weights, strict=True)
    )
    sigma2 = rss / effective_df
    covariance_diag = _inverse_diagonal(xtwx)
    standard_errors = {
        feature: math.sqrt(max(0.0, sigma2 * covariance_diag[index]))
        for index, feature in enumerate(feature_names)
    }
    return (
        {feature: coefs[index] for index, feature in enumerate(feature_names)},
        standard_errors,
    )


def _solve_with_jitter(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    jitter = 0.0
    for _attempt in range(6):
        candidate = [row.copy() for row in matrix]
        if jitter:
            for index in range(len(candidate)):
                candidate[index][index] += jitter
        try:
            return _solve_linear_system(candidate, rhs.copy())
        except ValueError:
            jitter = 1.0e-10 if jitter == 0.0 else jitter * 10.0
    raise ValueError("weighted regression system is singular")


def _inverse_diagonal(matrix: list[list[float]]) -> list[float]:
    diag: list[float] = []
    size = len(matrix)
    for index in range(size):
        basis = [0.0 for _ in range(size)]
        basis[index] = 1.0
        solution = _solve_with_jitter(matrix, basis)
        diag.append(solution[index])
    return diag


def _solve_linear_system(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    n = len(rhs)
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError("matrix must be square and match rhs length")

    for pivot_index in range(n):
        pivot_row = max(
            range(pivot_index, n),
            key=lambda row_index: abs(matrix[row_index][pivot_index]),
        )
        if abs(matrix[pivot_row][pivot_index]) < 1.0e-14:
            raise ValueError("singular linear system")
        if pivot_row != pivot_index:
            matrix[pivot_index], matrix[pivot_row] = matrix[pivot_row], matrix[pivot_index]
            rhs[pivot_index], rhs[pivot_row] = rhs[pivot_row], rhs[pivot_index]

        pivot = matrix[pivot_index][pivot_index]
        for column in range(pivot_index, n):
            matrix[pivot_index][column] /= pivot
        rhs[pivot_index] /= pivot

        for row_index in range(n):
            if row_index == pivot_index:
                continue
            factor = matrix[row_index][pivot_index]
            if factor == 0.0:
                continue
            for column in range(pivot_index, n):
                matrix[row_index][column] -= factor * matrix[pivot_index][column]
            rhs[row_index] -= factor * rhs[pivot_index]
    return rhs


def _finite(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result
