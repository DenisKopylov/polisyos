"""Compute base calibration losses before measurement-aware reweighting.

These helpers operate on simulated trace arrays and observed target arrays
only. Observation trust, coverage, lag, censoring, and regime discounts are
layered on top by `calibration.measurement` and auxiliary loss components.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import jax.numpy as jnp

from polisyos.foundry._numeric import NumericDomain, epsilon_for, finite_loss_or_inf
from polisyos.ir.analytics.calibration import TargetLossConfig


def _huber(x: jnp.ndarray, delta: float = 1.0) -> jnp.ndarray:
    abs_x = jnp.abs(x)
    quadratic = jnp.minimum(abs_x, delta)
    linear = abs_x - quadratic
    return 0.5 * quadratic**2 + delta * linear


def pointwise_base_loss(
    y_pred: jnp.ndarray,
    y_real: jnp.ndarray,
    cfg: TargetLossConfig,
    scale: float,
) -> jnp.ndarray:
    """Compute elementwise squared or Huber residual loss for one target series."""
    y_pred = jnp.asarray(y_pred, dtype=jnp.float32)
    y_real = jnp.asarray(y_real, dtype=jnp.float32)
    epsilon = max(float(cfg.epsilon), epsilon_for(NumericDomain.RELATIVE_LOSS))
    denom = jnp.asarray(scale + epsilon, dtype=y_pred.dtype)
    invalid = (
        ~jnp.all(jnp.isfinite(y_pred))
        | ~jnp.all(jnp.isfinite(y_real))
        | ~jnp.isfinite(denom)
        | (denom <= 0.0)
    )
    err = (y_pred - y_real) / denom
    if cfg.kind == "huber":
        loss = _huber(err)
    else:
        loss = jnp.square(err)
    inf_block = jnp.full_like(loss, jnp.inf)
    return jnp.where(invalid, inf_block, finite_loss_or_inf(loss))


def reduce_weighted_loss(
    pointwise_loss: jnp.ndarray,
    weights: jnp.ndarray | None,
    *,
    epsilon: float = 1e-8,
) -> jnp.ndarray:
    """Reduce a pointwise loss vector with optional non-negative weights.

    When all weights collapse to zero, the helper returns `0.0` instead of
    dividing by a near-zero total and injecting NaNs into the optimizer state.
    """
    pointwise_loss = jnp.asarray(pointwise_loss, dtype=jnp.float32)
    inf_value = jnp.asarray(jnp.inf, dtype=pointwise_loss.dtype)
    pointwise_finite = jnp.all(jnp.isfinite(pointwise_loss))
    if weights is None:
        reduced = finite_loss_or_inf(jnp.mean(pointwise_loss))
        return jnp.where(pointwise_finite, reduced, inf_value)
    weight_arr = jnp.asarray(weights, dtype=jnp.float32)
    weights_valid = jnp.all(jnp.isfinite(weight_arr)) & jnp.all(weight_arr >= 0.0)
    total_weight = jnp.sum(weight_arr)
    reduced = jnp.where(
        total_weight <= epsilon,
        jnp.array(0.0, dtype=jnp.float32),
        jnp.sum(pointwise_loss * weight_arr) / total_weight,
    )
    reduced = finite_loss_or_inf(reduced)
    return jnp.where(pointwise_finite & weights_valid, reduced, inf_value)


def compute_base_loss(
    y_pred: jnp.ndarray,
    y_real: jnp.ndarray,
    cfg: TargetLossConfig,
    scale: float,
) -> jnp.ndarray:
    """Compute an unweighted per-target loss scalar from predicted vs observed arrays."""
    return reduce_weighted_loss(
        pointwise_base_loss(y_pred, y_real, cfg, scale), None, epsilon=cfg.epsilon
    )


def loss_components(
    predicted: Mapping[str, jnp.ndarray],
    targets: Mapping[str, jnp.ndarray],
    configs: Mapping[str, TargetLossConfig],
    scales: Mapping[str, float],
    weights: Mapping[str, float] | None = None,
) -> tuple[jnp.ndarray, dict[str, jnp.ndarray], dict[str, jnp.ndarray]]:
    """Aggregate weighted calibration losses across all available targets.

    Returns:
        Tuple of `(total_loss, per_target_weighted_loss, per_target_base_loss)`.
    """
    total = jnp.array(0.0)
    per_target: dict[str, jnp.ndarray] = {}
    per_target_base: dict[str, jnp.ndarray] = {}
    for target_id, y_real in targets.items():
        if target_id not in predicted:
            continue
        y_pred = predicted[target_id]
        cfg = configs[target_id]
        scale = scales.get(target_id, 1.0) if cfg.relative else 1.0
        base_loss = compute_base_loss(y_pred, y_real, cfg, scale)
        weight = weights.get(target_id, cfg.weight) if weights is not None else cfg.weight
        if not math.isfinite(float(weight)) or float(weight) < 0.0:
            loss_val = jnp.asarray(jnp.inf, dtype=base_loss.dtype)
        else:
            loss_val = base_loss * float(weight)
        per_target_base[target_id] = base_loss
        per_target[target_id] = loss_val
        total = total + loss_val
    return finite_loss_or_inf(total), per_target, per_target_base


def unified_loss(
    predicted: Mapping[str, jnp.ndarray],
    targets: Mapping[str, jnp.ndarray],
    configs: Mapping[str, TargetLossConfig],
    scales: Mapping[str, float],
    weights: Mapping[str, float] | None = None,
) -> tuple[jnp.ndarray, dict[str, jnp.ndarray]]:
    """Return total loss plus per-target weighted losses for legacy callers."""
    total, per_target, _ = loss_components(predicted, targets, configs, scales, weights)
    return total, per_target
