"""Hessian computation with eigenvalue repair and finite-difference fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

import jax
import jax.numpy as jnp
import numpy as np


@dataclass(frozen=True)
class HessianResult:
    """Result of Hessian computation at an optimum."""

    hessian: np.ndarray  # (n, n) repaired Hessian
    covariance: np.ndarray  # (n, n) H^{-1}
    std: np.ndarray  # (n,) sqrt(diag(cov))
    eigenvalues: np.ndarray  # (n,) sorted eigenvalues from eigh
    condition_number: float
    n_repaired: int  # number of eigenvalues clipped to eps
    param_names: List[str]
    strategy: str  # "exact" or "finite_diff"


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
    param_names: List[str],
    *,
    damping: float = 1e-6,
    jitter_floor: float = 1e-8,
) -> HessianResult:
    """Compute Hessian of *loss_fn* at *flat_theta* with eigenvalue repair.

    Strategy:
    1. Try ``jax.hessian`` (exact, requires 2nd-order differentiability).
    2. Fallback: finite-difference Hessian.
    3. Eigenvalue repair: clip negative eigenvalues to *jitter_floor*.
    """
    strategy = "exact"
    try:
        H_raw = jax.hessian(loss_fn)(jnp.asarray(flat_theta))
        if not bool(jnp.all(jnp.isfinite(H_raw))):
            raise ValueError("Hessian contains non-finite values")
    except Exception:
        H_raw = _finite_difference_hessian(loss_fn, jnp.asarray(flat_theta))
        strategy = "finite_diff"
        if not bool(jnp.all(jnp.isfinite(H_raw))):
            raise ValueError("Finite-difference Hessian contains non-finite values")

    raw_eigvals = jnp.linalg.eigvalsh(0.5 * (H_raw + H_raw.T))
    H_repaired, eigvals, n_repaired = _repair_eigenvalues(
        H_raw,
        eps=jitter_floor,
        damping=damping,
    )

    cov = jnp.linalg.inv(H_repaired)

    std = jnp.sqrt(jnp.maximum(jnp.diag(cov), 0.0))
    if (
        not bool(jnp.all(jnp.isfinite(raw_eigvals)))
        or bool(jnp.any(raw_eigvals <= jitter_floor))
    ):
        condition_number = float("inf")
    else:
        condition_number = float(raw_eigvals[-1] / raw_eigvals[0])

    return HessianResult(
        hessian=np.asarray(H_repaired, dtype=float),
        covariance=np.asarray(cov, dtype=float),
        std=np.asarray(std, dtype=float),
        eigenvalues=np.asarray(eigvals, dtype=float),
        condition_number=condition_number,
        n_repaired=n_repaired,
        param_names=list(param_names),
        strategy=strategy,
    )
