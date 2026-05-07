"""Public numeric guardrails facade for Foundry runtime callers."""

from __future__ import annotations

from polisyos.foundry.execute._internal.numeric import (
    ACTOR_LOG_STD_MAX,
    ACTOR_LOG_STD_MIN,
    NumericDomain,
    clip_probability,
    decimal_from_numeric,
    economic_percent_delta,
    epsilon_for,
    finite_loss_or_inf,
    is_jax_tracer,
    require_finite_numpy,
    safe_exp_from_log_std,
    softplus_inverse,
    stable_logit,
    stable_normal_entropy,
    stable_normal_log_prob,
    symmetric_percent_delta,
    validate_quantile,
)

__all__ = [
    "ACTOR_LOG_STD_MAX",
    "ACTOR_LOG_STD_MIN",
    "NumericDomain",
    "clip_probability",
    "decimal_from_numeric",
    "economic_percent_delta",
    "epsilon_for",
    "finite_loss_or_inf",
    "is_jax_tracer",
    "require_finite_numpy",
    "safe_exp_from_log_std",
    "softplus_inverse",
    "stable_logit",
    "stable_normal_entropy",
    "stable_normal_log_prob",
    "symmetric_percent_delta",
    "validate_quantile",
]
