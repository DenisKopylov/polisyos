"""Stable Lex facade for runtime legal evaluation, NormPack assembly, and interventions.

The root package keeps imports lazy so lightweight consumers can inspect Lex contracts without
eagerly importing DuckDB, Foundry, or Scientist dependencies. Treat symbols exported through
``__all__`` as the stable public runtime surface. Offline legal preprocessing lives under
``polisyos.data_forge.domains.legal``.
"""

from __future__ import annotations

import importlib

__all__ = [
    "ActiveVersionResult",
    "ActiveVersionStrategy",
    "AffectedKPI",
    "ChangeProposalRef",
    "ComplianceDelta",
    "ComplianceTransition",
    "HierarchicalPolicySearchPlan",
    "InterventionKnobDictionaryEntry",
    "InterventionKnobSpec",
    "LegalEvaluationRequest",
    "LegalKnowledgeGraph",
    "LegalReportRef",
    "LexBenchmarkOutcome",
    "LexError",
    "LexFabricEvidencePath",
    "LexIndexError",
    "LexIngestError",
    "LexInterventionCompiler",
    "LexInterventionMapEntry",
    "LexNotReadyError",
    "LexPolicyBundleInput",
    "LexProvisionDirective",
    "LexProvisionMappingRegistry",
    "LexStructureError",
    "LexValidationError",
    "LexVersioningError",
    "MutationIntent",
    "NormChange",
    "NormChangeType",
    "NormDiff",
    "NormImpactAnalyzer",
    "NormImpactReport",
    "NormPackBudgets",
    "NormPackBuildRequest",
    "NormPackBuildResult",
    "NormPackMutator",
    "ProvisionProgramCrosswalkEntry",
    "StrategicResponseRegistryEntry",
    "StrategicResponseSpecRegistry",
    "TemporalInterventionSequencer",
    "TemporalInterventionStepInput",
    "assemble_norm_pack",
    "build_legal_authority_report",
    "build_legal_authority_requirement_artifact",
    "build_normative_applicability_report",
    "diff_norm_packs",
    "evaluate_legality",
    "lex_evidence_from_fabric_decision_data",
    "propose_changes",
    "resolve_active_version",
    "run_legal_benchmark",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # contracts
    "ChangeProposalRef": ("polisyos.core.contracts.lex", "ChangeProposalRef"),
    "LegalEvaluationRequest": ("polisyos.core.contracts.lex", "LegalEvaluationRequest"),
    "LegalReportRef": ("polisyos.core.contracts.lex", "LegalReportRef"),
    # api
    "assemble_norm_pack": ("polisyos.lex.api", "assemble_norm_pack"),
    "build_legal_authority_report": (
        "polisyos.lex.normpack",
        "build_legal_authority_report",
    ),
    "build_legal_authority_requirement_artifact": (
        "polisyos.lex.normpack",
        "build_legal_authority_requirement_artifact",
    ),
    "build_normative_applicability_report": (
        "polisyos.lex.normpack.applicability_report",
        "build_normative_applicability_report",
    ),
    "evaluate_legality": ("polisyos.lex.api", "evaluate_legality"),
    "propose_changes": ("polisyos.lex.api", "propose_changes"),
    "resolve_active_version": ("polisyos.lex.api", "resolve_active_version"),
    "LexBenchmarkOutcome": (
        "polisyos.lex.knowledge.benchmark",
        "LexBenchmarkOutcome",
    ),
    "run_legal_benchmark": (
        "polisyos.lex.knowledge.benchmark",
        "run_legal_benchmark",
    ),
    # errors
    "LexError": ("polisyos.lex.errors", "LexError"),
    "LexIndexError": ("polisyos.lex.errors", "LexIndexError"),
    "LexIngestError": ("polisyos.lex.errors", "LexIngestError"),
    "LexNotReadyError": ("polisyos.lex.errors", "LexNotReadyError"),
    "LexStructureError": ("polisyos.lex.errors", "LexStructureError"),
    "LexValidationError": ("polisyos.lex.errors", "LexValidationError"),
    "LexVersioningError": ("polisyos.lex.errors", "LexVersioningError"),
    "LexFabricEvidencePath": ("polisyos.lex.provenance", "LexFabricEvidencePath"),
    "lex_evidence_from_fabric_decision_data": (
        "polisyos.lex.provenance",
        "lex_evidence_from_fabric_decision_data",
    ),
    # types
    "ActiveVersionResult": ("polisyos.lex.types", "ActiveVersionResult"),
    "ActiveVersionStrategy": ("polisyos.lex.types", "ActiveVersionStrategy"),
    "NormPackBudgets": ("polisyos.lex.types", "NormPackBudgets"),
    "NormPackBuildRequest": ("polisyos.lex.types", "NormPackBuildRequest"),
    "NormPackBuildResult": ("polisyos.lex.types", "NormPackBuildResult"),
    # knowledge
    "LegalKnowledgeGraph": ("polisyos.lex.knowledge.search", "LegalKnowledgeGraph"),
    # interventions
    "HierarchicalPolicySearchPlan": (
        "polisyos.lex.interventions",
        "HierarchicalPolicySearchPlan",
    ),
    "InterventionKnobDictionaryEntry": (
        "polisyos.lex.intervention_artifacts",
        "InterventionKnobDictionaryEntry",
    ),
    "InterventionKnobSpec": ("polisyos.lex.interventions", "InterventionKnobSpec"),
    "LexInterventionMapEntry": (
        "polisyos.lex.intervention_artifacts",
        "LexInterventionMapEntry",
    ),
    "LexInterventionCompiler": ("polisyos.lex.interventions", "LexInterventionCompiler"),
    "LexPolicyBundleInput": (
        "polisyos.lex.intervention_artifacts",
        "LexPolicyBundleInput",
    ),
    "LexProvisionDirective": ("polisyos.lex.interventions", "LexProvisionDirective"),
    "LexProvisionMappingRegistry": (
        "polisyos.lex.intervention_artifacts",
        "LexProvisionMappingRegistry",
    ),
    "ProvisionProgramCrosswalkEntry": (
        "polisyos.lex.intervention_artifacts",
        "ProvisionProgramCrosswalkEntry",
    ),
    "StrategicResponseRegistryEntry": (
        "polisyos.lex.interventions",
        "StrategicResponseRegistryEntry",
    ),
    "StrategicResponseSpecRegistry": (
        "polisyos.lex.interventions",
        "StrategicResponseSpecRegistry",
    ),
    "TemporalInterventionSequencer": (
        "polisyos.lex.interventions",
        "TemporalInterventionSequencer",
    ),
    "TemporalInterventionStepInput": (
        "polisyos.lex.interventions",
        "TemporalInterventionStepInput",
    ),
    # simulator
    "AffectedKPI": ("polisyos.lex.simulator", "AffectedKPI"),
    "ComplianceDelta": ("polisyos.lex.simulator", "ComplianceDelta"),
    "ComplianceTransition": ("polisyos.lex.simulator", "ComplianceTransition"),
    "MutationIntent": ("polisyos.lex.simulator", "MutationIntent"),
    "NormChange": ("polisyos.lex.simulator", "NormChange"),
    "NormChangeType": ("polisyos.lex.simulator", "NormChangeType"),
    "NormDiff": ("polisyos.lex.simulator", "NormDiff"),
    "NormImpactAnalyzer": ("polisyos.lex.simulator", "NormImpactAnalyzer"),
    "NormImpactReport": ("polisyos.lex.simulator", "NormImpactReport"),
    "NormPackMutator": ("polisyos.lex.simulator", "NormPackMutator"),
    "diff_norm_packs": ("polisyos.lex.simulator", "diff_norm_packs"),
}


def __getattr__(name: str) -> object:
    """Load a public Lex symbol on first access.

    Args:
        name: Export name listed in ``__all__``.

    Returns:
        Imported symbol cached in this module's globals.

    Raises:
        AttributeError: If ``name`` is not part of the supported Lex facade.
    """
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.lex' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return eager globals plus lazy Lex exports for introspection tooling."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
