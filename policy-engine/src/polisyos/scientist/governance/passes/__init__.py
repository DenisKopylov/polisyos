"""Lazy facade for builtin Scientist governance passes and deprecated base contracts.

The facade keeps the stable class names used in docs and workflow configs while
loading each concrete pass only when requested. This avoids importing
artifact-heavy validators in processes that only need package discovery.
"""

from __future__ import annotations

from typing import Any

from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    IssueSeverity,
    PassContext,
    ValidatorPass,
)

__all__ = [
    "BudgetPass",
    "CheckpointPass",
    "ComplianceIssue",
    "ConfidencePass",
    "CrossGraphEvidencePass",
    "EquityPass",
    "FabricTrustGatePass",
    "FreshnessPass",
    "HumanReviewRequiredPass",
    "IncentiveCompatibilityPass",
    "IssueSeverity",
    "LegalPass",
    "LiteratureGatePass",
    "NormativeArbitrationPass",
    "PIICheckPass",
    "PassContext",
    "PrivacyPass",
    "QualityGatePass",
    "RefutationPass",
    "SafetyPass",
    "SchemaPass",
    "StrategicResponsePass",
    "SutvaCheckPass",
    "TransportabilityRequiredPass",
    "ValidatorPass",
]


def __getattr__(name: str) -> Any:
    """Resolve pass classes lazily and preserve the package-level contract."""
    if name == "BudgetPass":
        from .budget_pass import BudgetPass

        return BudgetPass
    if name == "CheckpointPass":
        from .checkpoint_pass import CheckpointPass

        return CheckpointPass
    if name == "ConfidencePass":
        from .confidence_pass import ConfidencePass

        return ConfidencePass
    if name == "CrossGraphEvidencePass":
        from .cross_graph_evidence_pass import CrossGraphEvidencePass

        return CrossGraphEvidencePass
    if name == "EquityPass":
        from .equity_pass import EquityPass

        return EquityPass
    if name == "FabricTrustGatePass":
        from .fabric_trust_gate_pass import FabricTrustGatePass

        return FabricTrustGatePass
    if name == "FreshnessPass":
        from .freshness_pass import FreshnessPass

        return FreshnessPass
    if name == "HumanReviewRequiredPass":
        from .human_review_pass import HumanReviewRequiredPass

        return HumanReviewRequiredPass
    if name == "IncentiveCompatibilityPass":
        from .incentive_compatibility_pass import IncentiveCompatibilityPass

        return IncentiveCompatibilityPass
    if name == "LegalPass":
        from .legal_pass import LegalPass

        return LegalPass
    if name == "LiteratureGatePass":
        from .literature_gate_pass import LiteratureGatePass

        return LiteratureGatePass
    if name == "NormativeArbitrationPass":
        from .normative_arbitration_pass import NormativeArbitrationPass

        return NormativeArbitrationPass
    if name == "PrivacyPass":
        from .privacy_pass import PrivacyPass

        return PrivacyPass
    if name == "PIICheckPass":
        from .pii_check_pass import PIICheckPass

        return PIICheckPass
    if name == "RefutationPass":
        from .refutation_pass import RefutationPass

        return RefutationPass
    if name == "QualityGatePass":
        from .quality_gate_pass import QualityGatePass

        return QualityGatePass
    if name == "SafetyPass":
        from .safety_pass import SafetyPass

        return SafetyPass
    if name == "SchemaPass":
        from .schema_pass import SchemaPass

        return SchemaPass
    if name == "StrategicResponsePass":
        from .strategic_response_pass import StrategicResponsePass

        return StrategicResponsePass
    if name == "SutvaCheckPass":
        from .sutva_check_pass import SutvaCheckPass

        return SutvaCheckPass
    if name == "TransportabilityRequiredPass":
        from .transportability_required_pass import TransportabilityRequiredPass

        return TransportabilityRequiredPass
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
