"""Bounded Explanation Reliability Layer public API."""

from __future__ import annotations

from polisyos.berl.contracts.explanation_bundle import ExplanationBundle
from polisyos.berl.contracts.validation_rules import (
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
    "EmpiricalBoundResult",
    "ExplanationBundle",
    "ExplanationOrchestrator",
    "ExplanationRequest",
    "ExplanationValidationResult",
    "ValidationThresholds",
    "empirical_bernstein_upper_bound",
    "estimate_local_infidelity",
    "hoeffding_upper_bound",
    "summarize_explanation_response",
    "validate_explanation_bundle",
]
