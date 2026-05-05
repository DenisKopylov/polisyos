"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
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
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ACTOR_LOG_STD_MAX": ("polisyos.foundry.runtime.numeric", "ACTOR_LOG_STD_MAX"),
    "ACTOR_LOG_STD_MIN": ("polisyos.foundry.runtime.numeric", "ACTOR_LOG_STD_MIN"),
    "NumericDomain": ("polisyos.foundry.runtime.numeric", "NumericDomain"),
    "clip_probability": ("polisyos.foundry.runtime.numeric", "clip_probability"),
    "decimal_from_numeric": ("polisyos.foundry.runtime.numeric", "decimal_from_numeric"),
    "economic_percent_delta": ("polisyos.foundry.runtime.numeric", "economic_percent_delta"),
    "epsilon_for": ("polisyos.foundry.runtime.numeric", "epsilon_for"),
    "finite_loss_or_inf": ("polisyos.foundry.runtime.numeric", "finite_loss_or_inf"),
    "is_jax_tracer": ("polisyos.foundry.runtime.numeric", "is_jax_tracer"),
    "require_finite_numpy": ("polisyos.foundry.runtime.numeric", "require_finite_numpy"),
    "safe_exp_from_log_std": ("polisyos.foundry.runtime.numeric", "safe_exp_from_log_std"),
    "softplus_inverse": ("polisyos.foundry.runtime.numeric", "softplus_inverse"),
    "stable_logit": ("polisyos.foundry.runtime.numeric", "stable_logit"),
    "stable_normal_entropy": ("polisyos.foundry.runtime.numeric", "stable_normal_entropy"),
    "stable_normal_log_prob": ("polisyos.foundry.runtime.numeric", "stable_normal_log_prob"),
    "symmetric_percent_delta": ("polisyos.foundry.runtime.numeric", "symmetric_percent_delta"),
    "validate_quantile": ("polisyos.foundry.runtime.numeric", "validate_quantile"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry._numeric' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
