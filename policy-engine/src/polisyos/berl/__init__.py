"""Bounded Explanation Reliability Layer public API."""

from __future__ import annotations

from polisyos.berl.adapters.conditional_shapley import (
    AffineModelProfileResolver,
    BoundedOutputProfileVerifier,
    ConditionalJointLaw,
    ConditionalLawBinding,
    ConditionalLawResolver,
    ConditionalModelVerifier,
    ConditionalSHAPAdapter,
    GaussianJointLaw,
    ResolvedConditionalLaw,
    VerifiedAffineModelProfile,
    VerifiedModelIdentity,
    VerifiedOutputBounds,
    WeightedFiniteSupportLaw,
)
from polisyos.berl.contracts.explanation_bundle import (
    ConditionalExplanationEvidence,
    ExplanationBundle,
)
from polisyos.berl.contracts.schema import validate_persisted_explanation_bundle
from polisyos.berl.contracts.validation_rules import (
    ConditionalEvidenceVerification,
    ConditionalEvidenceVerifier,
    ExplanationValidationResult,
    ValidationThresholds,
    summarize_explanation_response,
    validate_explanation_bundle,
)
from polisyos.berl.metrics.empirical_bounds import (
    EmpiricalBoundResult,
    empirical_bernstein_upper_bound,
    hoeffding_upper_bound,
)
from polisyos.berl.metrics.infidelity import estimate_local_infidelity
from polisyos.berl.service import ExplanationOrchestrator, ExplanationRequest

__all__ = [
    "AffineModelProfileResolver",
    "BoundedOutputProfileVerifier",
    "ConditionalEvidenceVerification",
    "ConditionalEvidenceVerifier",
    "ConditionalExplanationEvidence",
    "ConditionalJointLaw",
    "ConditionalLawBinding",
    "ConditionalLawResolver",
    "ConditionalModelVerifier",
    "ConditionalSHAPAdapter",
    "EmpiricalBoundResult",
    "ExplanationBundle",
    "ExplanationOrchestrator",
    "ExplanationRequest",
    "ExplanationValidationResult",
    "GaussianJointLaw",
    "ResolvedConditionalLaw",
    "ValidationThresholds",
    "VerifiedAffineModelProfile",
    "VerifiedModelIdentity",
    "VerifiedOutputBounds",
    "WeightedFiniteSupportLaw",
    "empirical_bernstein_upper_bound",
    "estimate_local_infidelity",
    "hoeffding_upper_bound",
    "summarize_explanation_response",
    "validate_explanation_bundle",
    "validate_persisted_explanation_bundle",
]
