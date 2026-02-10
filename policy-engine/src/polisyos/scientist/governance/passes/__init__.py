from __future__ import annotations

from typing import Any

from polisyos.core.governance.passes.base import ComplianceIssue, IssueSeverity, PassContext, ValidatorPass

__all__ = [
    "ComplianceIssue",
    "IssueSeverity",
    "PassContext",
    "ValidatorPass",
    "BudgetPass",
    "ConfidencePass",
    "EquityPass",
    "LegalPass",
    "PrivacyPass",
    "PIICheckPass",
    "QualityGatePass",
    "SafetyPass",
    "SchemaPass",
]


def __getattr__(name: str) -> Any:
    if name == "BudgetPass":
        from .budget_pass import BudgetPass

        return BudgetPass
    if name == "ConfidencePass":
        from .confidence_pass import ConfidencePass

        return ConfidencePass
    if name == "EquityPass":
        from .equity_pass import EquityPass

        return EquityPass
    if name == "LegalPass":
        from .legal_pass import LegalPass

        return LegalPass
    if name == "PrivacyPass":
        from .privacy_pass import PrivacyPass

        return PrivacyPass
    if name == "PIICheckPass":
        from .pii_check_pass import PIICheckPass

        return PIICheckPass
    if name == "QualityGatePass":
        from .quality_gate_pass import QualityGatePass

        return QualityGatePass
    if name == "SafetyPass":
        from .safety_pass import SafetyPass

        return SafetyPass
    if name == "SchemaPass":
        from .schema_pass import SchemaPass

        return SchemaPass
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
