"""Compute raw objective curvature and admit explicitly scoped inverse information."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import jax
import jax.numpy as jnp
import numpy as np


@dataclass(frozen=True)
class HessianResult:
    """Result of Hessian computation at an optimum."""

    hessian: np.ndarray  # (n, n) raw symmetric objective Hessian
    covariance: np.ndarray | None  # admitted inverse information, never repaired
    std: np.ndarray | None
    eigenvalues: np.ndarray  # (n,) sorted eigenvalues from eigh
    condition_number: float
    n_repaired: int  # compatibility field; compute_hessian never repairs eigenvalues
    param_names: list[str]
    strategy: str  # "exact" or "finite_diff"
    objective_kind: str = "generic_loss"
    covariance_kind: str | None = None
    covariance_unavailable_reason: str | None = None
    raw_rank: int = 0
    derivative_dtype: str = "unknown"
    fallback_reason: str | None = None
    gradient_norm: float | None = None
    objective_value: float | None = None
    objective_dtype: str | None = None
    objective_finite: bool | None = None


def _repair_eigenvalues(
    H: jnp.ndarray,
    eps: float = 1e-8,
    damping: float = 0.0,
) -> tuple[jnp.ndarray, jnp.ndarray, int]:
    """Symmetrize H, apply damping, clip non-positive eigenvalues, reconstruct.

    Returns (H_repaired, eigenvalues_clipped, n_repaired).
    """
    H_sym = 0.5 * (H + H.T)
    if damping:
        H_sym = H_sym + damping * jnp.eye(H_sym.shape[0], dtype=H_sym.dtype)
    eigvals, eigvecs = jnp.linalg.eigh(H_sym)
    n_repaired = int(jnp.sum(eigvals < eps))
    eigvals_clipped = jnp.maximum(eigvals, eps)
    H_repaired = eigvecs @ jnp.diag(eigvals_clipped) @ eigvecs.T
    return H_repaired, eigvals_clipped, n_repaired


def _finite_difference_hessian(
    loss_fn: Callable[[jnp.ndarray], jnp.ndarray],
    params: jnp.ndarray,
    eps: float = 1e-4,
) -> jnp.ndarray:
    """Central finite-difference Hessian approximation.

    Uses NumPy-space perturbations for stability even when JAX x64 is disabled.
    """
    params_np = np.asarray(params, dtype=np.float64).reshape(-1)
    n = params_np.shape[0]
    H = np.zeros((n, n), dtype=np.float64)

    try:
        params_dtype = jnp.asarray(params).dtype
    except Exception:
        params_dtype = jnp.float32

    fd_floor = float(np.sqrt(np.finfo(np.float32).eps))

    def _step_size(value: float) -> float:
        scale = max(1.0, abs(value))
        return max(float(eps) * scale, fd_floor * scale)

    def _eval(point: np.ndarray) -> float:
        value = loss_fn(jnp.asarray(point, dtype=params_dtype))
        return float(np.asarray(value, dtype=np.float64))

    try:
        grad_fn = jax.grad(loss_fn)
        for i in range(n):
            hi = _step_size(params_np[i])
            ei = np.zeros(n, dtype=np.float64)
            ei[i] = hi
            g_plus = np.asarray(
                grad_fn(jnp.asarray(params_np + ei, dtype=params_dtype)),
                dtype=np.float64,
            ).reshape(-1)
            g_minus = np.asarray(
                grad_fn(jnp.asarray(params_np - ei, dtype=params_dtype)),
                dtype=np.float64,
            ).reshape(-1)
            H[:, i] = (g_plus - g_minus) / (2.0 * hi)
        H = 0.5 * (H + H.T)
    except Exception:
        for i in range(n):
            hi = _step_size(params_np[i])
            ei = np.zeros(n, dtype=np.float64)
            ei[i] = hi
            for j in range(i, n):
                hj = _step_size(params_np[j])
                ej = np.zeros(n, dtype=np.float64)
                ej[j] = hj
                if i == j:
                    f_plus = _eval(params_np + ei)
                    f_0 = _eval(params_np)
                    f_minus = _eval(params_np - ei)
                    hij = (f_plus - 2.0 * f_0 + f_minus) / (hi * hi)
                else:
                    fpp = _eval(params_np + ei + ej)
                    fpm = _eval(params_np + ei - ej)
                    fmp = _eval(params_np - ei + ej)
                    fmm = _eval(params_np - ei - ej)
                    hij = (fpp - fpm - fmp + fmm) / (4.0 * hi * hj)
                H[i, j] = hij
                H[j, i] = hij
    return jnp.asarray(H)


def compute_hessian(
    loss_fn: Callable[[jnp.ndarray], jnp.ndarray],
    flat_theta: jnp.ndarray,
    param_names: list[str],
    *,
    damping: float = 1e-6,
    jitter_floor: float = 1e-8,
    objective_kind: Literal[
        "generic_loss", "negative_log_likelihood", "negative_log_posterior"
    ] = "generic_loss",
    condition_limit: float = 1e8,
    stationarity_tol: float = 1e-5,
) -> HessianResult:
    """Compute raw curvature, without turning repaired curvature into covariance.

    Generic objectives and finite differences are diagnostics. Inverse observed
    information or a local Laplace approximation is returned only for an explicit
    objective kind at a stationary, finite, positive, well-conditioned point.
    This numerical admission does not establish the declared probability model
    or its sampling assumptions. ``damping`` is retained for API compatibility;
    it cannot change the raw spectrum or an inferential covariance.
    """
    if not param_names or len(param_names) != len(set(param_names)):
        raise ValueError("ordered parameter names must be nonempty and unique")
    if objective_kind not in {"generic_loss", "negative_log_likelihood", "negative_log_posterior"}:
        raise ValueError("unsupported objective_kind")
    if not np.isfinite(jitter_floor) or jitter_floor < 0:
        raise ValueError("jitter_floor must be finite and nonnegative")
    if not np.isfinite(condition_limit) or condition_limit <= 1:
        raise ValueError("condition_limit must be finite and greater than one")
    if not np.isfinite(stationarity_tol) or stationarity_tol < 0:
        raise ValueError("stationarity_tol must be finite and nonnegative")
    if not np.isfinite(damping) or damping < 0:
        raise ValueError("damping must be finite and nonnegative")
    objective_value = None
    objective_dtype = None
    objective_finite = None
    try:
        objective = np.asarray(loss_fn(jnp.asarray(flat_theta)))
    except Exception:
        pass
    else:
        if objective.shape != () or np.iscomplexobj(objective):
            raise ValueError("Objective must return a real scalar")
        objective_dtype = str(objective.dtype)
        objective_finite = bool(np.isfinite(objective))
        if objective_finite:
            objective_value = float(objective)
    strategy = "exact"
    fallback_reason = None
    try:
        H_raw = jax.hessian(loss_fn)(jnp.asarray(flat_theta))
        if not bool(jnp.all(jnp.isfinite(H_raw))):
            raise ValueError("Hessian contains non-finite values")
    except Exception as exc:
        fallback_reason = f"{type(exc).__name__}: {exc}"
        H_raw = _finite_difference_hessian(loss_fn, jnp.asarray(flat_theta))
        strategy = "finite_diff"
        if not bool(jnp.all(jnp.isfinite(H_raw))):
            raise ValueError("Finite-difference Hessian contains non-finite values") from exc

    derivative_dtype = str(H_raw.dtype)
    hessian = np.asarray(H_raw, dtype=np.float64)
    hessian = 0.5 * (hessian + hessian.T)
    if hessian.shape != (len(param_names), len(param_names)):
        raise ValueError("Hessian axes must match ordered parameter names")
    raw_eigvals = np.linalg.eigvalsh(hessian)
    rank = int(np.sum(np.abs(raw_eigvals) > jitter_floor))
    if not np.all(np.isfinite(raw_eigvals)) or np.any(raw_eigvals <= jitter_floor):
        condition_number = float("inf")
    else:
        condition_number = float(raw_eigvals[-1] / raw_eigvals[0])

    gradient_norm = None
    try:
        gradient = np.asarray(jax.grad(loss_fn)(jnp.asarray(flat_theta)), dtype=float)
        gradient_norm = float(np.linalg.norm(gradient))
    except Exception:
        pass
    reason = None
    if objective_finite is None:
        reason = "objective_value_not_established"
    elif not objective_finite:
        reason = "nonfinite_objective"
    elif np.any(raw_eigvals < -jitter_floor):
        reason = "negative_curvature"
    elif rank < len(param_names) or np.any(raw_eigvals <= jitter_floor):
        reason = "singular_or_flat_curvature"
    elif condition_number > condition_limit:
        reason = "ill_conditioned_curvature"
    elif objective_kind == "generic_loss":
        reason = "generic_objective_curvature_only"
    elif strategy != "exact":
        reason = "finite_difference_diagnostic_only"
    elif gradient_norm is None or not np.isfinite(gradient_norm):
        reason = "stationarity_not_established"
    elif gradient_norm > stationarity_tol:
        reason = "nonstationary_point"
    covariance = None if reason is not None else np.linalg.inv(hessian)
    std = None if covariance is None else np.sqrt(np.diag(covariance))
    covariance_kind = None
    if covariance is not None:
        covariance_kind = (
            "inverse_observed_information"
            if objective_kind == "negative_log_likelihood"
            else "local_laplace_approximation"
        )
    return HessianResult(
        hessian=hessian,
        covariance=covariance,
        std=std,
        eigenvalues=raw_eigvals,
        condition_number=condition_number,
        n_repaired=0,
        param_names=list(param_names),
        strategy=strategy,
        objective_kind=objective_kind,
        covariance_kind=covariance_kind,
        covariance_unavailable_reason=reason,
        raw_rank=rank,
        derivative_dtype=derivative_dtype,
        fallback_reason=fallback_reason,
        gradient_norm=gradient_norm,
        objective_value=objective_value,
        objective_dtype=objective_dtype,
        objective_finite=objective_finite,
    )
