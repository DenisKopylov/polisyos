"""Public calibration loss module API."""
from __future__ import annotations

from typing import Dict, Mapping, Tuple

import jax.numpy as jnp

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
    """Pointwise base loss helper."""
    denom = scale + cfg.epsilon
    err = (y_pred - y_real) / denom
    if cfg.kind == "huber":
        return _huber(err)
    return jnp.square(err)


def reduce_weighted_loss(
    pointwise_loss: jnp.ndarray,
    weights: jnp.ndarray | None,
    *,
    epsilon: float = 1e-8,
) -> jnp.ndarray:
    """Reduce weighted loss helper."""
    if weights is None:
        return jnp.mean(pointwise_loss)
    clipped = jnp.clip(jnp.asarray(weights, dtype=jnp.float32), 0.0)
    total_weight = jnp.sum(clipped)
    return jnp.where(
        total_weight <= epsilon,
        jnp.array(0.0, dtype=jnp.float32),
        jnp.sum(pointwise_loss * clipped) / (total_weight + epsilon),
    )


def compute_base_loss(
    y_pred: jnp.ndarray,
    y_real: jnp.ndarray,
    cfg: TargetLossConfig,
    scale: float,
) -> jnp.ndarray:
    """Compute base loss helper."""
    return reduce_weighted_loss(pointwise_base_loss(y_pred, y_real, cfg, scale), None, epsilon=cfg.epsilon)


def loss_components(
    predicted: Mapping[str, jnp.ndarray],
    targets: Mapping[str, jnp.ndarray],
    configs: Mapping[str, TargetLossConfig],
    scales: Mapping[str, float],
    weights: Mapping[str, float] | None = None,
) -> Tuple[jnp.ndarray, Dict[str, jnp.ndarray], Dict[str, jnp.ndarray]]:
    """Loss components helper."""
    total = jnp.array(0.0)
    per_target: Dict[str, jnp.ndarray] = {}
    per_target_base: Dict[str, jnp.ndarray] = {}
    for target_id, y_real in targets.items():
        if target_id not in predicted:
            continue
        y_pred = predicted[target_id]
        cfg = configs[target_id]
        scale = scales.get(target_id, 1.0) if cfg.relative else 1.0
        base_loss = compute_base_loss(y_pred, y_real, cfg, scale)
        weight = weights.get(target_id, cfg.weight) if weights is not None else cfg.weight
        loss_val = weight * base_loss
        per_target_base[target_id] = base_loss
        per_target[target_id] = loss_val
        total = total + loss_val
    return total, per_target, per_target_base


def unified_loss(
    predicted: Mapping[str, jnp.ndarray],
    targets: Mapping[str, jnp.ndarray],
    configs: Mapping[str, TargetLossConfig],
    scales: Mapping[str, float],
    weights: Mapping[str, float] | None = None,
) -> Tuple[jnp.ndarray, Dict[str, jnp.ndarray]]:
    """Unified loss helper."""
    total, per_target, _ = loss_components(predicted, targets, configs, scales, weights)
    return total, per_target
