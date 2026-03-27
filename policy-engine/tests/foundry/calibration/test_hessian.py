from __future__ import annotations

from unittest.mock import patch

import jax
import jax.numpy as jnp
import numpy as np
import numpy.testing as npt

from polisyos.foundry.calibration.hessian import (
    HessianResult,
    _finite_difference_hessian,
    _repair_eigenvalues,
    compute_hessian,
)


def test_hessian_quadratic_function() -> None:
    """For f(x) = 0.5 * x^T A x, the Hessian should be A."""
    A = jnp.array([[4.0, 1.0], [1.0, 3.0]])

    def loss(x: jnp.ndarray) -> jnp.ndarray:
        return 0.5 * x @ A @ x

    x0 = jnp.zeros(2)
    result = compute_hessian(loss, x0, ["p0", "p1"], damping=0.0, jitter_floor=1e-12)

    assert result.strategy == "exact"
    npt.assert_allclose(result.hessian, np.asarray(A), atol=1e-5)
    # Covariance should be A^{-1}
    expected_cov = np.linalg.inv(np.asarray(A))
    npt.assert_allclose(result.covariance, expected_cov, atol=1e-5)
    assert result.n_repaired == 0
    assert result.condition_number > 1.0


def test_hessian_eigenvalue_repair() -> None:
    """A matrix with a negative eigenvalue should be repaired to PSD."""
    # Build a matrix with eigenvalues [5.0, -1.0]
    Q = jnp.array([[1.0, 0.0], [0.0, 1.0]])
    H_bad = Q @ jnp.diag(jnp.array([5.0, -1.0])) @ Q.T

    H_repaired, eigvals, n_repaired = _repair_eigenvalues(H_bad, eps=1e-8)

    assert n_repaired >= 1
    # All eigenvalues should now be >= eps
    eigvals_check = jnp.linalg.eigvalsh(H_repaired)
    assert bool(jnp.all(eigvals_check >= 1e-8 - 1e-12))


def test_finite_difference_matches_exact() -> None:
    """Finite-diff Hessian should closely match JAX exact for a smooth function."""
    A = jnp.array([[3.0, 0.5], [0.5, 2.0]], dtype=jnp.float64)

    def loss(x: jnp.ndarray) -> jnp.ndarray:
        return 0.5 * x @ A @ x

    x0 = jnp.array([1.0, -1.0], dtype=jnp.float64)
    H_exact = jax.hessian(loss)(x0)
    H_fd = _finite_difference_hessian(loss, x0, eps=1e-4)

    npt.assert_allclose(np.asarray(H_fd), np.asarray(H_exact), atol=1e-3)
