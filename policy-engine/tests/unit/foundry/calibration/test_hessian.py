from __future__ import annotations

from unittest.mock import patch

import jax
import jax.numpy as jnp
import numpy as np
import numpy.testing as npt

from polisyos.foundry.calibration.hessian import (
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
    result = compute_hessian(
        loss,
        x0,
        ["p0", "p1"],
        damping=0.0,
        jitter_floor=1e-12,
        objective_kind="negative_log_likelihood",
    )

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


def test_compute_hessian_reports_infinite_condition_for_singular_raw_hessian() -> None:
    def loss(x: jnp.ndarray) -> jnp.ndarray:
        return jnp.square(x[0])

    result = compute_hessian(loss, jnp.zeros(2), ["p0", "p1"], damping=0.0, jitter_floor=1e-8)

    assert result.condition_number == float("inf")
    assert result.n_repaired == 0
    assert result.covariance is None
    assert result.raw_rank == 1


def test_damping_does_not_repair_singular_information() -> None:
    hessian = jnp.diag(jnp.array([0.0, 2.0], dtype=jnp.float32))
    with patch("jax.hessian", return_value=lambda _: hessian):
        result = compute_hessian(
            lambda x: jnp.sum(x),
            jnp.zeros(2),
            ["p0", "p1"],
            damping=0.5,
            objective_kind="negative_log_likelihood",
        )
    npt.assert_array_equal(result.hessian, np.diag([0.0, 2.0]))
    assert result.covariance is None
    assert result.covariance_unavailable_reason == "singular_or_flat_curvature"


def test_gaussian_nll_independent_analytic_information_oracle() -> None:
    def objective(theta):
        return 0.5 * ((theta[0] - 1) ** 2 / 4 + (theta[1] - 2) ** 2 / 9)

    optimum = jnp.array([1.0, 2.0])
    npt.assert_allclose(jax.grad(objective)(optimum), [0.0, 0.0], atol=1e-7)
    result = compute_hessian(
        objective, optimum, ["a", "b"], objective_kind="negative_log_likelihood"
    )
    npt.assert_allclose(result.hessian, np.diag([1 / 4, 1 / 9]), rtol=1e-6)
    npt.assert_allclose(result.covariance, np.diag([4, 9]), rtol=1e-6)
    npt.assert_allclose(result.std, [2, 3], rtol=1e-6)
    assert result.covariance_kind == "inverse_observed_information"
    for step in [0.01, 0.005]:
        npt.assert_allclose(
            _finite_difference_hessian(objective, optimum, eps=step),
            np.diag([1 / 4, 1 / 9]),
            atol=1e-5,
        )


def test_same_curvature_generic_loss_has_no_covariance() -> None:
    result = compute_hessian(lambda x: 0.5 * jnp.sum(x * x), jnp.zeros(2), ["a", "b"])
    npt.assert_allclose(result.hessian, np.eye(2))
    assert result.covariance is None and result.std is None
    assert result.covariance_unavailable_reason == "generic_objective_curvature_only"


def test_saddle_raw_negative_direction_is_not_clipped() -> None:
    result = compute_hessian(
        lambda x: x[0] ** 2 - x[1] ** 2,
        jnp.zeros(2),
        ["a", "b"],
        objective_kind="negative_log_likelihood",
    )
    npt.assert_allclose(result.eigenvalues, [-2, 2])
    assert result.covariance is None
    assert result.covariance_unavailable_reason == "negative_curvature"


def test_nonstationary_likelihood_has_no_covariance() -> None:
    result = compute_hessian(
        lambda x: jnp.sum(x * x), jnp.ones(2), ["a", "b"], objective_kind="negative_log_likelihood"
    )
    assert result.covariance is None
    assert result.covariance_unavailable_reason == "nonstationary_point"


def test_covariance_property_removal_preserves_markers_but_breaks_oracle() -> None:
    import inspect

    import pytest

    from polisyos.foundry.calibration import hessian as module

    source = inspect.getsource(module.compute_hessian)
    source = source.replace(
        "covariance = None if reason is not None else np.linalg.inv(hessian)",
        "covariance = np.linalg.inv(hessian)",
    )
    namespace = dict(vars(module))
    exec(compile(source, "removed_covariance_admission", "exec"), namespace)
    mutant = namespace["compute_hessian"]

    def assert_generic_curvature_is_not_covariance(compute):
        result = compute(lambda x: 0.5 * jnp.sum(x * x), jnp.zeros(2), ["a", "b"])
        assert result.covariance is None

    assert_generic_curvature_is_not_covariance(module.compute_hessian)
    with pytest.raises(AssertionError):
        assert_generic_curvature_is_not_covariance(mutant)
