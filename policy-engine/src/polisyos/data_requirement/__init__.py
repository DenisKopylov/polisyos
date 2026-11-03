"""Data requirement compiler public API for W7.A Fabric refactors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._impl.models import (
    CAPABILITY_REQUIREMENT_RESOLUTION_SCHEMA_VERSION,
    DATA_REQUIREMENT_BASIS_SCHEMA_VERSION,
    DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION,
    DATA_REQUIREMENT_COMPILATION_V1_SCHEMA_VERSION,
    DATA_REQUIREMENT_SPEC_SCHEMA_VERSION,
    CapabilityBindingSnapshot,
    CapabilityRequirementResolution,
    DataQualityMinimums,
    DataRequirementBasisResolution,
    DataRequirementCompilationReport,
    DataRequirementCompilationReportV1,
    DataRequirementScope,
    DataRequirementSpec,
    data_requirement_authority_boundary,
    data_requirement_compilation_event_ref,
)

if TYPE_CHECKING:
    from polisyos.policy_grammar import (
        PolicyGrammarConceptSpineRefs as PolicyGrammarConceptSpineRefs,
    )
    from polisyos.policy_grammar import (
        PolicyGrammarIntent as PolicyGrammarIntent,
    )
    from polisyos.policy_grammar import (
        UniversalAuthorityProfile as UniversalAuthorityProfile,
    )

    from .compiler import (
        ClaimConstructDeclarationInputError,
        DataRequirementCompiler,
        ScenarioDomainInputError,
    )


def __getattr__(name: str) -> object:
    """Lazily expose compiler entrypoints and the owner types used by its bridge."""

    if name in {
        "PolicyGrammarConceptSpineRefs",
        "PolicyGrammarIntent",
        "UniversalAuthorityProfile",
    }:
        from polisyos.policy_grammar import (
            PolicyGrammarConceptSpineRefs,
            PolicyGrammarIntent,
            UniversalAuthorityProfile,
        )

        exports = {
            "PolicyGrammarConceptSpineRefs": PolicyGrammarConceptSpineRefs,
            "PolicyGrammarIntent": PolicyGrammarIntent,
            "UniversalAuthorityProfile": UniversalAuthorityProfile,
        }
        return exports[name]

    if name in {
        "DataRequirementCompiler",
        "ScenarioDomainInputError",
        "ClaimConstructDeclarationInputError",
        "compile_data_requirements_for_scenario",
        "parse_data_requirement_compilation_report",
        "data_requirement_compilation_audit_surface",
        "write_data_requirement_compilation_report",
    }:
        from .compiler import (
            ClaimConstructDeclarationInputError,
            DataRequirementCompiler,
            ScenarioDomainInputError,
            compile_data_requirements_for_scenario,
            data_requirement_compilation_audit_surface,
            parse_data_requirement_compilation_report,
            write_data_requirement_compilation_report,
        )

        exports = {
            "DataRequirementCompiler": DataRequirementCompiler,
            "ScenarioDomainInputError": ScenarioDomainInputError,
            "ClaimConstructDeclarationInputError": ClaimConstructDeclarationInputError,
            "compile_data_requirements_for_scenario": compile_data_requirements_for_scenario,
            "parse_data_requirement_compilation_report": parse_data_requirement_compilation_report,
            "data_requirement_compilation_audit_surface": (
                data_requirement_compilation_audit_surface
            ),
            "write_data_requirement_compilation_report": (
                write_data_requirement_compilation_report
            ),
        }
        return exports[name]
    raise AttributeError(f"module 'polisyos.data_requirement' has no attribute {name!r}")


__all__ = [
    "CAPABILITY_REQUIREMENT_RESOLUTION_SCHEMA_VERSION",
    "DATA_REQUIREMENT_BASIS_SCHEMA_VERSION",
    "DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION",
    "DATA_REQUIREMENT_COMPILATION_V1_SCHEMA_VERSION",
    "DATA_REQUIREMENT_SPEC_SCHEMA_VERSION",
    "CapabilityBindingSnapshot",
    "CapabilityRequirementResolution",
    "ClaimConstructDeclarationInputError",
    "DataQualityMinimums",
    "DataRequirementBasisResolution",
    "DataRequirementCompilationReport",
    "DataRequirementCompilationReportV1",
    "DataRequirementCompiler",
    "DataRequirementScope",
    "DataRequirementSpec",
    "ScenarioDomainInputError",
    "compile_data_requirements_for_scenario",
    "data_requirement_authority_boundary",
    "data_requirement_compilation_audit_surface",
    "data_requirement_compilation_event_ref",
    "parse_data_requirement_compilation_report",
    "write_data_requirement_compilation_report",
]
