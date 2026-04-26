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
    smallest_singular_value_i_minus_j: float | None
    near_fold: bool
    near_flip: bool
    near_loss_of_stability: bool
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
    fold_singular_value_threshold: float = 1.0e-3,
    stability_radius_tolerance: float = 5.0e-2,
    flip_eigenvalue_tolerance: float = 5.0e-2,
) -> JacobianSummary:
    """Compute spectral and conditioning summaries for a fixed-point map Jacobian."""

    array = np.asarray(matrix, dtype=float)
    notes: list[str] = []
    eigenvalues: np.ndarray | None = None
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
        fixed_point_system = np.eye(array.shape[0]) - array
        condition_number = float(np.linalg.cond(fixed_point_system))
    except np.linalg.LinAlgError:
        condition_number = None
        notes.append("condition_number_failed")

    try:
        singular_values = np.linalg.svd(np.eye(array.shape[0]) - array, compute_uv=False)
        smallest_singular_value_i_minus_j = float(np.min(singular_values))
    except np.linalg.LinAlgError:
        smallest_singular_value_i_minus_j = None
        notes.append("singular_values_failed")

    near_fold = bool(
        smallest_singular_value_i_minus_j is not None
        and smallest_singular_value_i_minus_j <= fold_singular_value_threshold
    )
    if near_fold:
        notes.append("near_fold")

    near_flip = bool(
        eigenvalues is not None
        and any(abs(complex(value) + 1.0) <= flip_eigenvalue_tolerance for value in eigenvalues)
    )
    if near_flip:
        notes.append("near_flip")

    near_loss_of_stability = bool(
        spectral_radius is not None
        and abs(spectral_radius - 1.0) <= stability_radius_tolerance
    )
    if near_loss_of_stability:
        notes.append("near_loss_of_stability")

    near_bifurcation = bool(
        (spectral_radius is not None and spectral_radius >= near_bifurcation_threshold)
        or near_fold
        or near_flip
        or near_loss_of_stability
    )
    if near_bifurcation:
        notes.append("near_bifurcation")

    return JacobianSummary(
        matrix=array,
        spectral_radius=spectral_radius,
        operator_norm_inf=operator_norm_inf,
        condition_number=condition_number,
        smallest_singular_value_i_minus_j=smallest_singular_value_i_minus_j,
        near_fold=near_fold,
        near_flip=near_flip,
        near_loss_of_stability=near_loss_of_stability,
        near_bifurcation=near_bifurcation,
        notes=tuple(notes),
    )
