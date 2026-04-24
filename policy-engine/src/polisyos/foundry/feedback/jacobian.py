"""Finite-difference Jacobian helpers and fixed-point spectral diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable

    from .config import PreparedFeedbackConfig


@dataclass(frozen=True)
class JacobianSummary:
    """Numeric Jacobian and derived stability diagnostics."""

    matrix: np.ndarray
    spectral_radius: float | None
    operator_norm_inf: float | None
    condition_number: float | None
    near_bifurcation: bool
    notes: tuple[str, ...] = ()


def finite_difference_jacobian(
    evaluate_map: Callable[[np.ndarray], np.ndarray],
    x: np.ndarray,
    *,
    prepared: PreparedFeedbackConfig,
    baseline_map: np.ndarray | None = None,
) -> np.ndarray:
    """Estimate the Jacobian of the fixed-point map with forward differences."""

    point = np.asarray(x, dtype=float)
    base = (
        np.asarray(baseline_map, dtype=float) if baseline_map is not None else evaluate_map(point)
    )
    dim = point.shape[0]
    jacobian = np.zeros((dim, dim), dtype=float)
    for index in range(dim):
        step = np.zeros_like(point)
        h = prepared.finite_difference_steps[index]
        step[index] = h
        perturbed = evaluate_map(point + step)
        jacobian[:, index] = (np.asarray(perturbed, dtype=float) - base) / h
    return jacobian


def summarize_jacobian(
    matrix: np.ndarray,
    *,
    near_bifurcation_threshold: float = 0.98,
) -> JacobianSummary:
    """Compute spectral and conditioning summaries for a fixed-point map Jacobian."""

    array = np.asarray(matrix, dtype=float)
    notes: list[str] = []
    try:
        eigenvalues = np.linalg.eigvals(array)
        spectral_radius = float(np.max(np.abs(eigenvalues)))
    except np.linalg.LinAlgError:
        spectral_radius = None
        notes.append("eigvals_failed")

    try:
        operator_norm_inf = float(np.linalg.norm(array, ord=np.inf))
    except np.linalg.LinAlgError:
        operator_norm_inf = None
        notes.append("operator_norm_failed")

    try:
        condition_number = float(np.linalg.cond(np.eye(array.shape[0]) - array))
    except np.linalg.LinAlgError:
        condition_number = None
        notes.append("condition_number_failed")

    near_bifurcation = bool(
        spectral_radius is not None and spectral_radius >= near_bifurcation_threshold
    )
    if near_bifurcation:
        notes.append("near_bifurcation")

    return JacobianSummary(
        matrix=array,
        spectral_radius=spectral_radius,
        operator_norm_inf=operator_norm_inf,
        condition_number=condition_number,
        near_bifurcation=near_bifurcation,
        notes=tuple(notes),
    )
