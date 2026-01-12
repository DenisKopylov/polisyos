from __future__ import annotations

from typing import Dict, Mapping, Tuple

import jax.numpy as jnp

from polisyos.ir.calibration import TargetLossConfig


def _huber(x: jnp.ndarray, delta: float = 1.0) -> jnp.ndarray:
    abs_x = jnp.abs(x)
    quadratic = jnp.minimum(abs_x, delta)
    linear = abs_x - quadratic
    return 0.5 * quadratic**2 + delta * linear


def unified_loss(
    predicted: Mapping[str, jnp.ndarray],
    targets: Mapping[str, jnp.ndarray],
    configs: Mapping[str, TargetLossConfig],
    scales: Mapping[str, float],
) -> Tuple[jnp.ndarray, Dict[str, jnp.ndarray]]:
    total = jnp.array(0.0)
    per_target: Dict[str, jnp.ndarray] = {}
    for target_id, y_real in targets.items():
        if target_id not in predicted:
            continue
        y_pred = predicted[target_id]
        cfg = configs[target_id]
        scale = scales.get(target_id, 1.0) if cfg.relative else 1.0
        denom = scale + cfg.epsilon
        err = (y_pred - y_real) / denom
        if cfg.kind == "huber":
            loss_val = jnp.mean(_huber(err))
        else:
            loss_val = jnp.mean(jnp.square(err))
        loss_val = cfg.weight * loss_val
        per_target[target_id] = loss_val
        total = total + loss_val
    return total, per_target
