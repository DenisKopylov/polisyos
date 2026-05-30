"""Typed Scholar support requirement compiler public surface."""

from __future__ import annotations

from polisyos.scholar_requirement._impl.compiler import (
    CollapseDimension,
    ScholarClaimRequirementSeed,
    ScholarDependentCorpusCollapseRule,
    ScholarPublicationTier,
    ScholarRequirementCompilationInput,
    ScholarSupportRequirementCompilationResult,
    ScholarSupportRequirementCompiler,
    ScholarSupportRequirementSpec,
    build_scholar_capability_requirement_bindings,
    normalize_scholar_support_requirement_specs,
    requirement_specs_by_claim,
    scholar_support_requirement_audit_surface,
    scholar_support_requirement_authority_boundary,
    write_scholar_support_requirement_result,
)

__all__ = [
    "CollapseDimension",
    "ScholarClaimRequirementSeed",
    "ScholarDependentCorpusCollapseRule",
    "ScholarPublicationTier",
    "ScholarRequirementCompilationInput",
    "ScholarSupportRequirementCompilationResult",
    "ScholarSupportRequirementCompiler",
    "ScholarSupportRequirementSpec",
    "build_scholar_capability_requirement_bindings",
    "normalize_scholar_support_requirement_specs",
    "requirement_specs_by_claim",
    "scholar_support_requirement_audit_surface",
    "scholar_support_requirement_authority_boundary",
    "write_scholar_support_requirement_result",
]
