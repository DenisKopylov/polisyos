"""Data requirement compiler public API for W7.A Fabric refactors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._impl.models import (
    DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION,
    DATA_REQUIREMENT_SPEC_SCHEMA_VERSION,
    DataQualityMinimums,
    DataRequirementCompilationReport,
    DataRequirementScope,
    DataRequirementSpec,
    data_requirement_authority_boundary,
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

    from .compiler import DataRequirementCompiler


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
        "compile_data_requirements_for_scenario",
        "data_requirement_compilation_audit_surface",
        "write_data_requirement_compilation_report",
    }:
        from .compiler import (
            DataRequirementCompiler,
            compile_data_requirements_for_scenario,
            data_requirement_compilation_audit_surface,
            write_data_requirement_compilation_report,
        )

        exports = {
            "DataRequirementCompiler": DataRequirementCompiler,
            "compile_data_requirements_for_scenario": compile_data_requirements_for_scenario,
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
    "DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION",
    "DATA_REQUIREMENT_SPEC_SCHEMA_VERSION",
    "DataQualityMinimums",
    "DataRequirementCompilationReport",
    "DataRequirementCompiler",
    "DataRequirementScope",
    "DataRequirementSpec",
    "compile_data_requirements_for_scenario",
    "data_requirement_authority_boundary",
    "data_requirement_compilation_audit_surface",
    "write_data_requirement_compilation_report",
]
