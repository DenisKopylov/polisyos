"""Data requirement compiler public API for W7.A Fabric refactors."""

from __future__ import annotations

import importlib
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
        compile_data_requirements_for_scenario,
        compiled_requirements_for_world_slot,
        data_requirement_compilation_audit_surface,
        parse_data_requirement_compilation_report,
        persist_model_input_compilation_report,
        verify_model_input_compilation_report,
        write_data_requirement_compilation_report,
    )
    from .model_input_requirements import ModelInputCompilationReport as ModelInputCompilationReport

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "PolicyGrammarConceptSpineRefs": (
        "polisyos.policy_grammar",
        "PolicyGrammarConceptSpineRefs",
    ),
    "PolicyGrammarIntent": ("polisyos.policy_grammar", "PolicyGrammarIntent"),
    "UniversalAuthorityProfile": ("polisyos.policy_grammar", "UniversalAuthorityProfile"),
    "ClaimConstructDeclarationInputError": (
        "polisyos.data_requirement.compiler",
        "ClaimConstructDeclarationInputError",
    ),
    "DataRequirementCompiler": (
        "polisyos.data_requirement.compiler",
        "DataRequirementCompiler",
    ),
    "ScenarioDomainInputError": (
        "polisyos.data_requirement.compiler",
        "ScenarioDomainInputError",
    ),
    "compile_data_requirements_for_scenario": (
        "polisyos.data_requirement.compiler",
        "compile_data_requirements_for_scenario",
    ),
    "compiled_requirements_for_world_slot": (
        "polisyos.data_requirement.compiler",
        "compiled_requirements_for_world_slot",
    ),
    "data_requirement_compilation_audit_surface": (
        "polisyos.data_requirement.compiler",
        "data_requirement_compilation_audit_surface",
    ),
    "parse_data_requirement_compilation_report": (
        "polisyos.data_requirement.compiler",
        "parse_data_requirement_compilation_report",
    ),
    "persist_model_input_compilation_report": (
        "polisyos.data_requirement.compiler",
        "persist_model_input_compilation_report",
    ),
    "verify_model_input_compilation_report": (
        "polisyos.data_requirement.compiler",
        "verify_model_input_compilation_report",
    ),
    "write_data_requirement_compilation_report": (
        "polisyos.data_requirement.compiler",
        "write_data_requirement_compilation_report",
    ),
    "ModelInputCompilationReport": (
        "polisyos.data_requirement.model_input_requirements",
        "ModelInputCompilationReport",
    ),
}


def __getattr__(name: str) -> object:
    """Lazily expose compiler entrypoints and the owner types used by its bridge."""
    owner = _LAZY_IMPORTS.get(name)
    if owner is None:
        raise AttributeError(f"module 'polisyos.data_requirement' has no attribute {name!r}")
    module_name, attr_name = owner
    return getattr(importlib.import_module(module_name), attr_name)


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
    "ModelInputCompilationReport",
    "ScenarioDomainInputError",
    "compile_data_requirements_for_scenario",
    "compiled_requirements_for_world_slot",
    "data_requirement_authority_boundary",
    "data_requirement_compilation_audit_surface",
    "data_requirement_compilation_event_ref",
    "parse_data_requirement_compilation_report",
    "persist_model_input_compilation_report",
    "verify_model_input_compilation_report",
    "write_data_requirement_compilation_report",
]
