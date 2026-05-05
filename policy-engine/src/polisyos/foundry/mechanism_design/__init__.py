"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "build_reserve_auction_welfare_loss_bound",
    "certify_affine_tax",
    "certify_license_scoring_auction",
    "certify_piecewise_linear_tax",
    "get_mechanism_family_spec",
    "mechanism_family_catalog",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "build_reserve_auction_welfare_loss_bound": (
        "polisyos.foundry.mechanisms.design",
        "build_reserve_auction_welfare_loss_bound",
    ),
    "certify_affine_tax": ("polisyos.foundry.mechanisms.design", "certify_affine_tax"),
    "certify_license_scoring_auction": (
        "polisyos.foundry.mechanisms.design",
        "certify_license_scoring_auction",
    ),
    "certify_piecewise_linear_tax": (
        "polisyos.foundry.mechanisms.design",
        "certify_piecewise_linear_tax",
    ),
    "get_mechanism_family_spec": (
        "polisyos.foundry.mechanisms.design",
        "get_mechanism_family_spec",
    ),
    "mechanism_family_catalog": ("polisyos.foundry.mechanisms.design", "mechanism_family_catalog"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.foundry.mechanism_design' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
