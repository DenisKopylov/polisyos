from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np
import numpy.testing as npt

from polisyos.foundry.calibration.bijectors import (
    Bijector,
    affine_bijector,
    chain_bijector,
    inverse_bijector,
    log_bijector,
    logit_bijector,
    make_bijector,
    softplus_bijector,
)


def test_log_roundtrip() -> None:
    b = log_bijector()
    x = jnp.array([0.1, 1.0, 5.0, 100.0])
    u = b.inverse(x)
    x_reconstructed = b.forward(u)
    npt.assert_allclose(np.asarray(x_reconstructed), np.asarray(x), rtol=1e-5)


def test_logit_roundtrip() -> None:
    b = logit_bijector()
    x = jnp.array([0.01, 0.25, 0.5, 0.75, 0.99])
    u = b.inverse(x)
    x_reconstructed = b.forward(u)
    npt.assert_allclose(np.asarray(x_reconstructed), np.asarray(x), rtol=1e-4)


def test_softplus_roundtrip() -> None:
    b = softplus_bijector(lower=2.0)
    x = jnp.array([2.5, 3.0, 10.0])
    u = b.inverse(x)
    x_reconstructed = b.forward(u)
    npt.assert_allclose(np.asarray(x_reconstructed), np.asarray(x), rtol=1e-5)


def test_affine_roundtrip() -> None:
    b = affine_bijector(loc=3.0, scale=2.0)
    u = jnp.array([-1.0, 0.0, 1.0, 5.0])
    x = b.forward(u)
    u_reconstructed = b.inverse(x)
    npt.assert_allclose(np.asarray(u_reconstructed), np.asarray(u), rtol=1e-6)


def test_chain_bijector_composition() -> None:
    """chain(log, affine(0, 2)) should give 2*exp(u)."""
    b = chain_bijector(log_bijector(), affine_bijector(loc=0.0, scale=2.0))
    u = jnp.array([0.0, 1.0, -1.0])
    expected = 2.0 * jnp.exp(u)
    npt.assert_allclose(np.asarray(b.forward(u)), np.asarray(expected), rtol=1e-5)
    # roundtrip
    x = b.forward(u)
    npt.assert_allclose(np.asarray(b.inverse(x)), np.asarray(u), rtol=1e-5)


def test_inverse_is_left_inverse() -> None:
    """inverse_bijector(b).forward(b.forward(x)) == x for several bijectors."""
    bijectors = [
        log_bijector(),
        logit_bijector(),
        softplus_bijector(lower=1.0),
        affine_bijector(loc=5.0, scale=-3.0),
    ]
    u = jnp.array([0.5, 1.0, 2.0])
    for b in bijectors:
        inv_b = inverse_bijector(b)
        x = b.forward(u)
        u_recovered = inv_b.forward(x)
        npt.assert_allclose(
            np.asarray(u_recovered), np.asarray(u), rtol=1e-4,
            err_msg=f"inverse_bijector failed for {b}",
        )


def test_log_det_jacobian_matches_numerical() -> None:
    """Compare analytic ldj to numerical log|d forward/du| for log bijector."""
    b = log_bijector()
    u = jnp.array(2.0)
    analytic_ldj = b.log_det_jacobian(u)
    # Numerical: log|d exp(u)/du| = log(exp(u)) = u
    numerical_ldj = jnp.log(jnp.abs(jax.grad(lambda v: b.forward(v))(u)))
    npt.assert_allclose(float(analytic_ldj), float(numerical_ldj), rtol=1e-5)


def test_make_bijector_backward_compat() -> None:
    """Existing make_bijector still works and now has ldj populated."""
    b = make_bijector(lower=0.0, upper=1.0)
    u = jnp.array(0.0)
    x = b.forward(u)
    assert 0.0 <= float(x) <= 1.0
    assert b.log_det_jacobian is not None
    ldj_val = b.log_det_jacobian(u)
    assert jnp.isfinite(ldj_val)


def test_make_bijector_rejects_non_increasing_bounds() -> None:
    with np.testing.assert_raises(ValueError):
        make_bijector(lower=1.0, upper=1.0)


def test_bounded_bijector_inverse_stays_finite_near_boundaries() -> None:
    b = make_bijector(lower=0.0, upper=1.0)
    x = jnp.array([1e-12, 1.0 - 1e-12], dtype=jnp.float32)
    u = b.inverse(x)
    x_roundtrip = b.forward(u)
    assert bool(jnp.all(jnp.isfinite(u)))
    assert bool(jnp.all((x_roundtrip > 0.0) & (x_roundtrip < 1.0)))


def test_chain_ldj_accumulates_correctly() -> None:
    """Chain ldj should equal sum of individual ldjs at intermediate values."""
    b1 = log_bijector()
    b2 = affine_bijector(loc=0.0, scale=3.0)
    chain = chain_bijector(b1, b2)

    u = jnp.array(1.5)
    # Manual: ldj_1(u) + ldj_2(b1.forward(u))
    expected_ldj = b1.log_det_jacobian(u) + b2.log_det_jacobian(b1.forward(u))
    actual_ldj = chain.log_det_jacobian(u)
    npt.assert_allclose(float(actual_ldj), float(expected_ldj), rtol=1e-6)
