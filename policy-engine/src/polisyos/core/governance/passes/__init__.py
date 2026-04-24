"""Exports base governance-pass interfaces plus lazily loaded legal and safety passes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity

from .base import PassContext, ValidatorPass

if TYPE_CHECKING:
    from .legal_pass import LegalPass
    from .safety_pass import SafetyPass

__all__ = [
    "ComplianceIssue",
    "IssueSeverity",
    "LegalPass",
    "PassContext",
    "SafetyPass",
    "ValidatorPass",
]


def __getattr__(name: str) -> Any:
    if name == "LegalPass":
        from .legal_pass import LegalPass

        return LegalPass
    if name == "SafetyPass":
        from .safety_pass import SafetyPass

        return SafetyPass
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
