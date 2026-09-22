"""Canonical Foundry execution mechanisms.

The classes exported here own the live fiscal and labor patch kernels.  The
legacy ``polisyos.foundry.mechanisms`` modules remain compatibility facades
that re-export these same objects for existing callers.
"""

from polisyos.foundry.execute.mechanisms.fiscal import (
    IncomeTax,
    TaxSubsidy,
    compute_income_tax,
    compute_tax,
)
from polisyos.foundry.execute.mechanisms.labor import LaborMarketMechanism

__all__ = [
    "IncomeTax",
    "LaborMarketMechanism",
    "TaxSubsidy",
    "compute_income_tax",
    "compute_tax",
]
