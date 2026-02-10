from __future__ import annotations

from typing import Any

from .base import ComplianceIssue, IssueSeverity, PassContext, ValidatorPass

__all__ = [
    "ComplianceIssue",
    "IssueSeverity",
    "PassContext",
    "ValidatorPass",
    "LegalPass",
    "SafetyPass",
]


def __getattr__(name: str) -> Any:
    if name == "LegalPass":
        from .legal_pass import LegalPass

        return LegalPass
    if name == "SafetyPass":
        from .safety_pass import SafetyPass

        return SafetyPass
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
