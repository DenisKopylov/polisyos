"""
Legal compliance contracts for Policy OS.

Exports stable types for the legal validation subsystem.
Use these imports in consuming modules to avoid coupling
to internal implementation details.
"""

from __future__ import annotations

from polisyos.ir.norm_pack import NormPack, NormRef, NormRule, RuleType
from polisyos.scientist.governance.legal.backends.base import RuleBackend

__all__ = [
    "NormPack",
    "NormRule",
    "NormRef",
    "RuleType",
    "RuleBackend",
]
