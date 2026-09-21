"""Test-first witnesses for CAL-02 effective calibration loss semantics.

The tests keep the four CAL-02 boundaries explicit: exact axis contracts,
sample-quality versus target-priority weights, safe zero-support reduction, and
normalization over the observed training slice only.
"""

from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy.testing as npt
import pytest

from polisyos.foundry.calibration.calibrator import _compute_scale_local
from polisyos.foundry.calibration.loss import (
    loss_components,
    pointwise_base_loss,
    reduce_weighted_loss,
)
from polisyos.foundry.calibration.measurement import (
    MeasurementAwareLossConfig,
    compute_effective_weight,
)
from polisyos.ir.analytics.calibration import CalibrationTarget, TargetLossConfig

pytestmark = pytest.mark.unit


def _target(*, scale: str = "mean_abs") -> CalibrationTarget:
    """Build the smallest target accepted by the calibration scale helper."""
    return CalibrationTarget(
        target_id="target_cal02",
        model_metric_path="metrics.calibration_rate",
        loss=TargetLossConfig(relative=True, scale=scale),
    )


def test_pointwise_loss_rejects_ambiguous_vector_column_broadcast() -> None:
    """A vector and column must not silently become an N-by-N comparison."""
    cfg = TargetLossConfig(relative=False)

    with pytest.raises(ValueError, match="shape"):
        pointwise_base_loss(
            jnp.asarray([[0.0], [2.0]], dtype=jnp.float32),
            jnp.asarray([0.0, 2.0], dtype=jnp.float32),
            cfg,
            scale=1.0,
        )


def test_zero_effective_support_has_finite_primal_and_reverse_gradient() -> None:
    """Masked arithmetic stays finite while exposing explicit no-support state."""
    pointwise = jnp.asarray([1.0, 4.0], dtype=jnp.float32)
    weights = jnp.zeros_like(pointwise)

    loss = reduce_weighted_loss(pointwise, weights)
    objective = lambda value: reduce_weighted_loss(value**2, weights)
    value = jnp.asarray([1.0, 2.0], dtype=jnp.float32)
    gradient = jax.grad(objective)(value)
    jitted_loss = jax.jit(objective)(value)

    assert float(loss) == 0.0
    assert float(jitted_loss) == 0.0
    assert bool(jnp.all(jnp.isfinite(gradient)))

    adapted = compute_effective_weight(
        base_weights=1.0,
        trust_weight=jnp.ones(2, dtype=jnp.float32),
        coverage_estimate=jnp.zeros(2, dtype=jnp.float32),
        censoring_mask=None,
        lag_days_estimate=None,
        schema_regime_id=None,
        shock_mask=None,
        config=MeasurementAwareLossConfig(),
    )
    assert bool(adapted["has_effective_support"]) is False


def test_sample_quality_is_normalized_before_target_priority() -> None:
    """Changing target priority must not be canceled by within-target reduction."""
    pointwise = jnp.asarray([1.0, 9.0], dtype=jnp.float32)
    quality = compute_effective_weight(
        base_weights=1.0,
        trust_weight=jnp.asarray([1.0, 0.0], dtype=jnp.float32),
        coverage_estimate=jnp.ones(2, dtype=jnp.float32),
        censoring_mask=None,
        lag_days_estimate=None,
        schema_regime_id=None,
        shock_mask=None,
        config=MeasurementAwareLossConfig(),
    )
    normalized = reduce_weighted_loss(pointwise, quality["sample_quality_weight"])

    npt.assert_allclose(float(normalized * 9.0), 9.0, atol=1e-6)
    npt.assert_allclose(float(normalized * 1.0), 1.0, atol=1e-6)
    npt.assert_allclose(quality["effective_weight"], jnp.asarray([1.0, 0.0]))


def test_inter_target_priority_changes_the_shared_objective() -> None:
    """Target priorities remain outside each target's sample reduction."""
    cfg = TargetLossConfig(relative=False)
    predicted = {"a": jnp.asarray([1.0]), "b": jnp.asarray([9.0])}
    targets = {"a": jnp.asarray([0.0]), "b": jnp.asarray([0.0])}

    high_a, _, _ = loss_components(
        predicted,
        targets,
        {"a": cfg, "b": cfg},
        {"a": 1.0, "b": 1.0},
        weights={"a": 9.0, "b": 1.0},
    )
    high_b, _, _ = loss_components(
        predicted,
        targets,
        {"a": cfg, "b": cfg},
        {"a": 1.0, "b": 1.0},
        weights={"a": 1.0, "b": 9.0},
    )

    assert float(high_a) == pytest.approx(90.0)
    assert float(high_b) == pytest.approx(730.0)


def test_scale_uses_observed_training_mask_not_placeholder_dates() -> None:
    """A second target's placeholder dates cannot halve target A's scale."""
    values = jnp.asarray([10.0, 10.0, 0.0, 0.0], dtype=jnp.float32)
    observed_mask = jnp.asarray([True, True, False, False])
    training_mask = jnp.asarray([True, True, False, False])

    scale = _compute_scale_local(
        values,
        _target(),
        observed_mask=observed_mask,
        training_mask=training_mask,
    )

    npt.assert_allclose(scale, 10.0, atol=1e-6)


def test_mask_shape_is_checked_before_scale_arithmetic() -> None:
    """A mask with a different axis cannot be broadcast into a scale."""
    with pytest.raises(ValueError, match="shape"):
        _compute_scale_local(
            jnp.ones(2, dtype=jnp.float32),
            _target(),
            observed_mask=jnp.ones((2, 1), dtype=bool),
            training_mask=jnp.ones(2, dtype=bool),
        )
