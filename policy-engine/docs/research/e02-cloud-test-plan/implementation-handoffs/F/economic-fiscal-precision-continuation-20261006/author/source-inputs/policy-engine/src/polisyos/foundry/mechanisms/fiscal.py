"""Compatibility facade for the canonical fiscal execution mechanisms."""

from polisyos.foundry.execute.mechanisms.fiscal import (
    IncomeTax,
    TaxSubsidy,
    compute_income_tax,
    compute_tax,
)

__all__ = ["IncomeTax", "TaxSubsidy", "compute_income_tax", "compute_tax"]
