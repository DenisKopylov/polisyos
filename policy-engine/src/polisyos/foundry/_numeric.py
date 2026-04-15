"""Shared numeric guardrails for Foundry runtime, calibration, and analytics.

This module centralizes domain-specific epsilon policies, finite-value
validation, stable scalar conversions, and a handful of common transforms used
across calibration, constraints, reward shaping, and reporting code.
"""
from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np


class NumericDomain(str, Enum):
    """Semantic domains that need consistent epsilon and clipping policies."""

    PROBABILITY = "probability"
    POSITIVE = "positive"
    RELATIVE_LOSS = "relative_loss"
    DECIMAL = "decimal"
    UTILITY = "utility"
    PERCENT_DELTA = "percent_delta"


_DOMAIN_EPSILON: dict[NumericDomain, float] = {
    NumericDomain.PROBABILITY: 1e-6,
    NumericDomain.POSITIVE: 1e-8,
    NumericDomain.RELATIVE_LOSS: 1e-8,
    NumericDomain.DECIMAL: 1e-12,
    NumericDomain.UTILITY: 1e-6,
    NumericDomain.PERCENT_DELTA: 1e-12,
}

ACTOR_LOG_STD_MIN = -20.0
ACTOR_LOG_STD_MAX = 5.0


def epsilon_for(domain: NumericDomain) -> float:
    """Return the canonical epsilon for a numeric domain."""
    return _DOMAIN_EPSILON[domain]


def clip_probability(
    value: jnp.ndarray | float,
    *,
    eps: float | None = None,
) -> jnp.ndarray:
    """Clamp probabilities symmetrically away from 0 and 1."""
    epsilon = eps if eps is not None else epsilon_for(NumericDomain.PROBABILITY)
    return jnp.clip(jnp.asarray(value), epsilon, 1.0 - epsilon)


def stable_logit(
    value: jnp.ndarray | float,
    *,
    eps: float | None = None,
) -> jnp.ndarray:
    """Stable logit with symmetric boundary clipping."""
    clipped = clip_probability(value, eps=eps)
    return jnp.log(clipped) - jnp.log1p(-clipped)


def softplus_inverse(
    value: jnp.ndarray | float,
    *,
    eps: float | None = None,
) -> jnp.ndarray:
    """Numerically stable inverse of ``softplus`` on strictly positive inputs."""
    epsilon = eps if eps is not None else epsilon_for(NumericDomain.POSITIVE)
    safe = jnp.maximum(jnp.asarray(value), epsilon)
    threshold = jnp.array(20.0, dtype=safe.dtype)
    large_branch = safe + jnp.log1p(-jnp.exp(-safe))
    small_branch = jnp.log(jnp.expm1(safe))
    return jnp.where(safe > threshold, large_branch, small_branch)


def safe_exp_from_log_std(log_std: jnp.ndarray | float) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Clip actor log-stds to a finite training range before exponentiation."""
    clipped = jnp.clip(jnp.asarray(log_std), ACTOR_LOG_STD_MIN, ACTOR_LOG_STD_MAX)
    return clipped, jnp.exp(clipped)


def stable_normal_log_prob(
    actions: jnp.ndarray,
    mean: jnp.ndarray,
    log_std: jnp.ndarray,
) -> jnp.ndarray:
    """Compute diagonal-Gaussian log-probabilities without variance overflow."""
    clipped_log_std, _ = safe_exp_from_log_std(log_std)
    quadratic = jnp.sum(
        jnp.square(actions - mean) * jnp.exp(-2.0 * clipped_log_std),
        axis=-1,
    )
    normalizer = jnp.sum(jnp.log(2.0 * jnp.pi) + 2.0 * clipped_log_std, axis=-1)
    return -0.5 * (quadratic + normalizer)


def stable_normal_entropy(log_std: jnp.ndarray) -> jnp.ndarray:
    """Compute diagonal-Gaussian entropy after clipping log-stds."""
    clipped_log_std, _ = safe_exp_from_log_std(log_std)
    return 0.5 * jnp.sum(
        1.0 + jnp.log(2.0 * jnp.pi) + 2.0 * clipped_log_std,
        axis=-1,
    )


def symmetric_percent_delta(
    before: float | np.ndarray,
    after: float | np.ndarray,
    *,
    eps: float | None = None,
) -> float:
    """Return a bounded symmetric percent change that is defined at zero/negative baselines."""
    epsilon = eps if eps is not None else epsilon_for(NumericDomain.PERCENT_DELTA)
    before_f = float(np.asarray(before, dtype=np.float64))
    after_f = float(np.asarray(after, dtype=np.float64))
    if not math.isfinite(before_f) or not math.isfinite(after_f):
        raise ValueError("percent delta inputs must be finite")
    denom = abs(before_f) + abs(after_f)
    if denom <= epsilon:
        return 0.0
    return float(200.0 * (after_f - before_f) / denom)


def economic_percent_delta(
    before: float | np.ndarray,
    after: float | np.ndarray,
    *,
    eps: float | None = None,
) -> float:
    """Return a stable economic percent change.

    Positive baselines retain the familiar asymmetric interpretation. Zero,
    negative, and debt-like baselines fall back to the bounded symmetric
    percentage change so reports stay defined and sign-consistent.
    """
    epsilon = eps if eps is not None else epsilon_for(NumericDomain.PERCENT_DELTA)
    before_f = float(np.asarray(before, dtype=np.float64))
    after_f = float(np.asarray(after, dtype=np.float64))
    if not math.isfinite(before_f) or not math.isfinite(after_f):
        raise ValueError("percent delta inputs must be finite")
    if before_f > epsilon and after_f >= 0.0:
        return float((after_f - before_f) / before_f * 100.0)
    return symmetric_percent_delta(before_f, after_f, eps=epsilon)


def require_finite_numpy(values: Any, *, label: str) -> np.ndarray:
    """Materialize a NumPy array and fail closed on NaN/Inf."""
    arr = np.asarray(values)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{label} must be finite")
    return arr


def finite_loss_or_inf(loss: jnp.ndarray) -> jnp.ndarray:
    """Convert NaN/Inf loss outputs into explicit +inf fail-closed sentinels."""
    arr = jnp.asarray(loss)
    inf_value = jnp.asarray(jnp.inf, dtype=arr.dtype)
    return jnp.where(jnp.all(jnp.isfinite(arr)), arr, inf_value)


def decimal_from_numeric(value: Any, *, label: str = "value") -> Decimal:
    """Convert one numeric scalar to ``Decimal`` without silent NaN/Inf coercion."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric, got bool")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, np.integer):
        return Decimal(int(value))
    if isinstance(value, str):
        text = value.strip()
        try:
            return Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"{label} must be numeric") from exc

    arr = np.asarray(value)
    if arr.ndim != 0:
        raise ValueError(f"{label} must be scalar")
    if np.issubdtype(arr.dtype, np.integer):
        return Decimal(int(arr))
    if np.issubdtype(arr.dtype, np.floating):
        scalar = np.float64(arr)
        if not np.isfinite(scalar):
            raise ValueError(f"{label} must be finite")
        magnitude = abs(float(scalar))
        if magnitude == 0.0 or 1e-6 <= magnitude < 1e16:
            text = np.format_float_positional(
                scalar,
                unique=True,
                precision=17,
                trim="-",
            )
            if "." not in text:
                text = f"{text}.0"
        else:
            text = np.format_float_scientific(
                scalar,
                unique=True,
                precision=17,
                trim="-",
            )
        return Decimal(text)
    raise ValueError(f"{label} must be numeric")


def validate_quantile(
    quantile: float | None,
    *,
    label: str = "quantile",
    default: float = 0.5,
) -> float:
    """Validate a quantile parameter eagerly before delegating to NumPy/JAX."""
    q = default if quantile is None else float(quantile)
    if not math.isfinite(q):
        raise ValueError(f"{label} must be finite")
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"{label} must lie in [0, 1]")
    return q


def is_jax_tracer(value: Any) -> bool:
    """Return True when *value* is a JAX tracer and cannot be eagerly validated."""
    return isinstance(value, jax.core.Tracer)
