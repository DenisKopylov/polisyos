"""Public foundry agent metrics module API."""
from __future__ import annotations

from typing import Any, Mapping

import jax.numpy as jnp


def normalize_action(action_val: jnp.ndarray, action_space: Mapping[str, Any] | None) -> jnp.ndarray:
    """Normalize action helper."""
    if not action_space:
        return jnp.clip(action_val, 0.0, 1.0)
    range_spec = action_space.get("range")
    if not isinstance(range_spec, (list, tuple)) or len(range_spec) != 2:
        return jnp.clip(action_val, 0.0, 1.0)
    try:
        lower = float(range_spec[0])
        upper = float(range_spec[1])
    except (TypeError, ValueError):
        return jnp.clip(action_val, 0.0, 1.0)
    width = upper - lower
    if width <= 0:
        return jnp.clip(action_val, 0.0, 1.0)
    return jnp.clip((action_val - lower) / width, 0.0, 1.0)


def policy_entropy(action_prob: jnp.ndarray, epsilon: float = 1e-6) -> jnp.ndarray:
    """Policy entropy helper."""
    clipped = jnp.clip(action_prob, epsilon, 1.0 - epsilon)
    return -jnp.mean(clipped * jnp.log(clipped) + (1.0 - clipped) * jnp.log(1.0 - clipped))


def saturation_rate(action_prob: jnp.ndarray, epsilon: float = 1e-3) -> jnp.ndarray:
    """Saturation rate helper."""
    return jnp.mean((action_prob <= epsilon) | (action_prob >= 1.0 - epsilon))


def risk_action_correlation(
    risk_aversion: jnp.ndarray, action_prob: jnp.ndarray, epsilon: float = 1e-6
) -> jnp.ndarray:
    """Risk action correlation helper."""
    risk_mean = jnp.mean(risk_aversion)
    action_mean = jnp.mean(action_prob)
    risk_std = jnp.std(risk_aversion)
    action_std = jnp.std(action_prob)
    denom = risk_std * action_std + epsilon
    cov = jnp.mean((risk_aversion - risk_mean) * (action_prob - action_mean))
    return cov / denom


def risk_action_gap(
    risk_aversion: jnp.ndarray, action_prob: jnp.ndarray, *, top_frac: float = 0.2
) -> jnp.ndarray:
    """Risk action gap helper."""
    n_agents = int(risk_aversion.shape[0])
    if n_agents <= 0:
        return jnp.array(0.0, dtype=jnp.float32)
    frac = float(top_frac)
    if frac <= 0.0:
        return jnp.array(0.0, dtype=jnp.float32)
    frac = min(frac, 0.5)
    k = max(1, int(n_agents * frac))
    idx = jnp.argsort(risk_aversion)
    low_idx = idx[:k]
    high_idx = idx[-k:]
    return jnp.mean(action_prob[high_idx]) - jnp.mean(action_prob[low_idx])
