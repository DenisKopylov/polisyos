"""Compatibility facade for Phase 3 mechanism-family and certificate helpers."""

from __future__ import annotations

from polisyos.foundry.methods.catalog.mechanism.families import (
    get_mechanism_family_spec,
    mechanism_family_catalog,
)
from polisyos.ir.analytics.mechanism_design import (
    ICVerificationMode,
    MechanismFamily,
    MechanismFamilySpec,
    build_reserve_auction_welfare_loss_bound,
    certify_affine_tax,
    certify_license_scoring_auction,
    certify_piecewise_linear_tax,
)


__all__ = [
    "build_reserve_auction_welfare_loss_bound",
    "certify_affine_tax",
    "certify_license_scoring_auction",
    "certify_piecewise_linear_tax",
    "get_mechanism_family_spec",
    "mechanism_family_catalog",
]
