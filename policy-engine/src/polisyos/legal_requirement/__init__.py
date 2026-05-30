"""Legal authority requirement compiler public facade."""

from __future__ import annotations

from polisyos.legal_requirement._impl.compiler import (
    LegalAuthorityRequirementCompiler,
    compile_legal_authority_requirement_artifact,
    compile_legal_authority_requirements,
    legal_authority_requirement_audit_surface,
    write_legal_authority_requirement_artifact,
)
from polisyos.legal_requirement._impl.models import (
    LEGAL_AUTHORITY_REQUIREMENT_ARTIFACT_SCHEMA_VERSION,
    LEGAL_AUTHORITY_REQUIREMENT_COMPILER_RULE_VERSION,
    LEGAL_AUTHORITY_REQUIREMENT_SPEC_SCHEMA_VERSION,
    LEGAL_REQUIREMENT_PATTERN_REFS,
    LegalAdmissibilityGrade,
    LegalAuthorityRequirementArtifact,
    LegalAuthorityRequirementSpec,
    LegalAuthorityType,
    LegalRequirementFallbackMode,
    LegalRequirementFallbackPolicy,
    LegalScopePredicates,
    TemporalCompetenceWindow,
    legal_authority_requirement_authority_boundary,
    normalize_legal_authority_type,
)

__all__ = [
    "LEGAL_AUTHORITY_REQUIREMENT_ARTIFACT_SCHEMA_VERSION",
    "LEGAL_AUTHORITY_REQUIREMENT_COMPILER_RULE_VERSION",
    "LEGAL_AUTHORITY_REQUIREMENT_SPEC_SCHEMA_VERSION",
    "LEGAL_REQUIREMENT_PATTERN_REFS",
    "LegalAdmissibilityGrade",
    "LegalAuthorityRequirementArtifact",
    "LegalAuthorityRequirementCompiler",
    "LegalAuthorityRequirementSpec",
    "LegalAuthorityType",
    "LegalRequirementFallbackMode",
    "LegalRequirementFallbackPolicy",
    "LegalScopePredicates",
    "TemporalCompetenceWindow",
    "compile_legal_authority_requirement_artifact",
    "compile_legal_authority_requirements",
    "legal_authority_requirement_audit_surface",
    "legal_authority_requirement_authority_boundary",
    "normalize_legal_authority_type",
    "write_legal_authority_requirement_artifact",
]
