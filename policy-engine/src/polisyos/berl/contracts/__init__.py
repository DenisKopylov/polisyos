"""Contracts for BERL explanation bundles and product gates."""

from __future__ import annotations

from polisyos.berl.contracts.display_policy import (
    can_show_bare_bar_chart,
    explanation_limitation_message,
)
from polisyos.berl.contracts.explanation_bundle import (
    EXPLANATION_BUNDLE_SCHEMA_VERSION,
    ExplanationBundle,
    MethodExplanation,
    bundle_json_schema,
)
from polisyos.berl.contracts.schema import (
    explanation_bundle_schema_id,
    generated_explanation_bundle_schema,
    write_explanation_bundle_schema,
)
from polisyos.berl.contracts.validation_rules import (
    ExplanationValidationResult,
    ValidationThresholds,
    summarize_explanation_response,
    validate_explanation_bundle,
)

__all__ = [
    "EXPLANATION_BUNDLE_SCHEMA_VERSION",
    "ExplanationBundle",
    "ExplanationValidationResult",
    "MethodExplanation",
    "ValidationThresholds",
    "bundle_json_schema",
    "can_show_bare_bar_chart",
    "explanation_bundle_schema_id",
    "explanation_limitation_message",
    "generated_explanation_bundle_schema",
    "summarize_explanation_response",
    "validate_explanation_bundle",
    "write_explanation_bundle_schema",
]
