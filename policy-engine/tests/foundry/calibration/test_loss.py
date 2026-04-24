from __future__ import annotations

import jax.numpy as jnp
import numpy.testing as npt

from polisyos.foundry.calibration.loss import (
    _huber,
    compute_base_loss,
    loss_components,
    reduce_weighted_loss,
)
from polisyos.ir.analytics.calibration import TargetLossConfig


class TestHuber:
    def test_huber_quadratic_regime(self) -> None:
        x = jnp.array([0.1, 0.5, 0.9])
        delta = 1.0
        result = _huber(x, delta)
        expected = 0.5 * x**2
        npt.assert_allclose(result, expected, atol=1e-6)

    def test_huber_linear_regime(self) -> None:
        x = jnp.array([2.0, 5.0, 10.0])
        delta = 1.0
        result = _huber(x, delta)
        expected = delta * (jnp.abs(x) - 0.5 * delta)
        npt.assert_allclose(result, expected, atol=1e-6)


class TestComputeBaseLoss:
    def test_compute_base_loss_mse_mode(self) -> None:
        y_pred = jnp.array([1.0, 2.0, 3.0])
        y_real = jnp.array([1.1, 2.2, 2.8])
        cfg = TargetLossConfig(kind="mse", weight=1.0, relative=False, epsilon=1e-8)
        result = compute_base_loss(y_pred, y_real, cfg, scale=1.0)
        err = y_pred - y_real
        expected = jnp.mean(jnp.square(err))
        npt.assert_allclose(float(result), float(expected), atol=1e-6)

    def test_compute_base_loss_fails_closed_on_non_finite_inputs(self) -> None:
        cfg = TargetLossConfig(kind="mse", weight=1.0, relative=False, epsilon=1e-8)
        result = compute_base_loss(jnp.array([1.0, jnp.nan]), jnp.array([1.0, 2.0]), cfg, scale=1.0)
        assert jnp.isinf(result)


class TestReduceWeightedLoss:
    def test_returns_zero_when_all_weights_collapse_to_zero(self) -> None:
        reduced = reduce_weighted_loss(
            jnp.array([1.0, 2.0, 3.0], dtype=jnp.float32),
            jnp.zeros(3, dtype=jnp.float32),
            epsilon=1e-8,
        )
        assert float(reduced) == 0.0

    def test_rejects_negative_or_non_finite_weights(self) -> None:
        pointwise = jnp.array([1.0, 2.0], dtype=jnp.float32)
        assert jnp.isinf(reduce_weighted_loss(pointwise, jnp.array([1.0, -1.0]), epsilon=1e-8))
        assert jnp.isinf(reduce_weighted_loss(pointwise, jnp.array([1.0, jnp.nan]), epsilon=1e-8))


class TestLossComponents:
    def test_loss_components_weighted_sum(self) -> None:
        predicted = {"gdp": jnp.array([1.0, 2.0]), "cpi": jnp.array([3.0, 4.0])}
        targets = {"gdp": jnp.array([1.1, 2.1]), "cpi": jnp.array([3.2, 3.9])}
        cfg = TargetLossConfig(kind="mse", weight=1.0, relative=False, epsilon=1e-8)
        configs = {"gdp": cfg, "cpi": cfg}
        scales = {"gdp": 1.0, "cpi": 1.0}
        weights = {"gdp": 2.0, "cpi": 0.5}

        total, per_target, per_target_base = loss_components(
            predicted,
            targets,
            configs,
            scales,
            weights=weights,
        )

        reconstructed = sum(per_target.values())
        npt.assert_allclose(float(total), float(reconstructed), atol=1e-6)

        for tid in per_target:
            expected_weighted = weights[tid] * per_target_base[tid]
            npt.assert_allclose(float(per_target[tid]), float(expected_weighted), atol=1e-6)

    def test_loss_components_reject_invalid_override_weight(self) -> None:
        predicted = {"gdp": jnp.array([1.0, 2.0])}
        targets = {"gdp": jnp.array([1.0, 2.0])}
        cfg = TargetLossConfig(kind="mse", weight=1.0, relative=False, epsilon=1e-8)
        total, per_target, _ = loss_components(
            predicted,
            targets,
            {"gdp": cfg},
            {"gdp": 1.0},
            weights={"gdp": -0.5},
        )

        assert jnp.isinf(total)
        assert jnp.isinf(per_target["gdp"])
