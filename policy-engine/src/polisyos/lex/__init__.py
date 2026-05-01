"""Stable Lex facade for legal corpus ingestion, NormPack assembly, and intervention APIs.

The root package keeps imports lazy so lightweight consumers can inspect Lex contracts without
eagerly importing DuckDB, Foundry, or Scientist dependencies. Treat symbols exported through
``__all__`` as the stable public surface for the ``ingest -> structure -> version index ->
normpack -> legal evaluation`` pipeline and for legal-to-policy intervention compilation.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "ActiveVersionResult",
    "ActiveVersionStrategy",
    "AffectedKPI",
    "ChangeProposalRef",
    "ComplianceDelta",
    "ComplianceTransition",
    "HierarchicalPolicySearchAdapter",
    "HierarchicalPolicySearchPlan",
    "InterventionKnobDictionaryEntry",
    "InterventionKnobSpec",
    "LegalDocSource",
    "LegalEvaluationRequest",
    "LegalKnowledgeGraph",
    "LegalReportRef",
    "LexError",
    "LexFabricEvidencePath",
    "LexIndexError",
    "LexIngestError",
    "LexIngestOptions",
    "LexIngestResult",
    "LexInterventionCompiler",
    "LexInterventionMapEntry",
    "LexNotReadyError",
    "LexPolicyBundleInput",
    "LexProvisionDirective",
    "LexProvisionMappingRegistry",
    "LexStructureError",
    "LexStructureOptions",
    "LexStructureResult",
    "LexValidationError",
    "LexVersionIndexOptions",
    "LexVersionIndexResult",
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
    "TemporalInterventionSequenceCompileResult",
    "TemporalInterventionSequenceCompiler",
    "TemporalInterventionSequencer",
    "TemporalInterventionStepInput",
    "WorldEventRefLike",
    "assemble_norm_pack",
    "build_legal_structure",
    "build_version_index",
    "diff_norm_packs",
    "evaluate_legality",
    "ingest_legal_doc_bytes",
    "lex_evidence_from_fabric_decision_data",
    "propose_changes",
    "resolve_active_version",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # contracts
    "ChangeProposalRef": ("polisyos.core.contracts.lex", "ChangeProposalRef"),
    "LegalEvaluationRequest": ("polisyos.core.contracts.lex", "LegalEvaluationRequest"),
    "LegalReportRef": ("polisyos.core.contracts.lex", "LegalReportRef"),
    # api
    "assemble_norm_pack": ("polisyos.lex.api", "assemble_norm_pack"),
    "build_legal_structure": ("polisyos.lex.api", "build_legal_structure"),
    "build_version_index": ("polisyos.lex.api", "build_version_index"),
    "evaluate_legality": ("polisyos.lex.api", "evaluate_legality"),
    "ingest_legal_doc_bytes": ("polisyos.lex.api", "ingest_legal_doc_bytes"),
    "propose_changes": ("polisyos.lex.api", "propose_changes"),
    "resolve_active_version": ("polisyos.lex.api", "resolve_active_version"),
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
    "LegalDocSource": ("polisyos.lex.types", "LegalDocSource"),
    "LexIngestOptions": ("polisyos.lex.types", "LexIngestOptions"),
    "LexIngestResult": ("polisyos.lex.types", "LexIngestResult"),
    "LexStructureOptions": ("polisyos.lex.types", "LexStructureOptions"),
    "LexStructureResult": ("polisyos.lex.types", "LexStructureResult"),
    "LexVersionIndexOptions": ("polisyos.lex.types", "LexVersionIndexOptions"),
    "LexVersionIndexResult": ("polisyos.lex.types", "LexVersionIndexResult"),
    "NormPackBudgets": ("polisyos.lex.types", "NormPackBudgets"),
    "NormPackBuildRequest": ("polisyos.lex.types", "NormPackBuildRequest"),
    "NormPackBuildResult": ("polisyos.lex.types", "NormPackBuildResult"),
    "WorldEventRefLike": ("polisyos.lex.types", "WorldEventRefLike"),
    # knowledge
    "LegalKnowledgeGraph": ("polisyos.lex.knowledge.search", "LegalKnowledgeGraph"),
    # interventions
    "HierarchicalPolicySearchAdapter": (
        "polisyos.lex.interventions",
        "HierarchicalPolicySearchAdapter",
    ),
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
    "TemporalInterventionSequenceCompiler": (
        "polisyos.lex.interventions",
        "TemporalInterventionSequenceCompiler",
    ),
    "TemporalInterventionSequenceCompileResult": (
        "polisyos.lex.interventions",
        "TemporalInterventionSequenceCompileResult",
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


def __getattr__(name: str) -> Any:
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
