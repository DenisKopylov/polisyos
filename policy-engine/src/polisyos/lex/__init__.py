"""Stable Lex facade for runtime legal evaluation, NormPack assembly, and interventions.

The root package keeps imports lazy so lightweight consumers can inspect Lex contracts without
eagerly importing DuckDB, Foundry, or Scientist dependencies. Treat symbols exported through
``__all__`` as the stable public runtime surface. Offline legal preprocessing lives under
``polisyos.data_forge.domains.legal``.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

__all__ = [
    "ActiveVersionResult",
    "ActiveVersionStrategy",
    "AffectedKPI",
    "ChangeProposalRef",
    "ComplianceDelta",
    "ComplianceTransition",
    "ConstraintSeverity",
    "HierarchicalPolicySearchPlan",
    "InterventionKnobDictionaryEntry",
    "InterventionKnobSpec",
    "LegalConstraint",
    "LegalConstraintBridge",
    "LegalConstraintSet",
    "LegalEvaluationRequest",
    "LegalKnowledgeGraph",
    "LegalReportRef",
    "LegalSourceRelationRefusal",
    "LegalSourceRelationVerificationMissingError",
    "LegalToDAGMapping",
    "LegalToDAGMappingType",
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
    "evaluate_transport_constraints",
    "is_transport_blocked",
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
    "ConstraintSeverity": (
        "polisyos.lex.legal_evaluation.transport_constraints",
        "ConstraintSeverity",
    ),
    "LegalConstraint": (
        "polisyos.lex.legal_evaluation.transport_constraints",
        "LegalConstraint",
    ),
    "LegalConstraintBridge": (
        "polisyos.lex.legal_evaluation.transport_constraints",
        "LegalConstraintBridge",
    ),
    "LegalConstraintSet": (
        "polisyos.lex.legal_evaluation.transport_constraints",
        "LegalConstraintSet",
    ),
    "LegalToDAGMapping": (
        "polisyos.lex.legal_evaluation.transport_constraints",
        "LegalToDAGMapping",
    ),
    "LegalToDAGMappingType": (
        "polisyos.lex.legal_evaluation.transport_constraints",
        "LegalToDAGMappingType",
    ),
    "LegalSourceRelationRefusal": (
        "polisyos.data_forge.read_api.legal",
        "LegalSourceRelationRefusal",
    ),
    "LegalSourceRelationVerificationMissingError": (
        "polisyos.data_forge.read_api.legal",
        "LegalSourceRelationVerificationMissingError",
    ),
    "is_transport_blocked": (
        "polisyos.lex.legal_evaluation.transport_constraints",
        "is_transport_blocked",
    ),
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
    "evaluate_transport_constraints": (
        "polisyos.lex.api",
        "evaluate_transport_constraints",
    ),
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
    "LexInterventionCompiler": (
        "polisyos.lex.interventions",
        "LexInterventionCompiler",
    ),
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


if TYPE_CHECKING:
    from polisyos.core.contracts.lex import (
        ChangeProposalRef as ChangeProposalRef,
    )
    from polisyos.core.contracts.lex import (
        LegalEvaluationRequest as LegalEvaluationRequest,
    )
    from polisyos.core.contracts.lex import (
        LegalReportRef as LegalReportRef,
    )
    from polisyos.data_forge.read_api.legal import (
        LegalSourceRelationRefusal as LegalSourceRelationRefusal,
    )
    from polisyos.data_forge.read_api.legal import (
        LegalSourceRelationVerificationMissingError as LegalSourceRelationVerificationMissingError,
    )
    from polisyos.lex.api import (
        assemble_norm_pack as assemble_norm_pack,
    )
    from polisyos.lex.api import (
        evaluate_legality as evaluate_legality,
    )
    from polisyos.lex.api import (
        evaluate_transport_constraints as evaluate_transport_constraints,
    )
    from polisyos.lex.api import (
        propose_changes as propose_changes,
    )
    from polisyos.lex.api import (
        resolve_active_version as resolve_active_version,
    )
    from polisyos.lex.errors import (
        LexError as LexError,
    )
    from polisyos.lex.errors import (
        LexIndexError as LexIndexError,
    )
    from polisyos.lex.errors import (
        LexIngestError as LexIngestError,
    )
    from polisyos.lex.errors import (
        LexNotReadyError as LexNotReadyError,
    )
    from polisyos.lex.errors import (
        LexStructureError as LexStructureError,
    )
    from polisyos.lex.errors import (
        LexValidationError as LexValidationError,
    )
    from polisyos.lex.errors import (
        LexVersioningError as LexVersioningError,
    )
    from polisyos.lex.intervention_artifacts import (
        InterventionKnobDictionaryEntry as InterventionKnobDictionaryEntry,
    )
    from polisyos.lex.intervention_artifacts import (
        LexInterventionMapEntry as LexInterventionMapEntry,
    )
    from polisyos.lex.intervention_artifacts import (
        LexPolicyBundleInput as LexPolicyBundleInput,
    )
    from polisyos.lex.intervention_artifacts import (
        LexProvisionMappingRegistry as LexProvisionMappingRegistry,
    )
    from polisyos.lex.intervention_artifacts import (
        ProvisionProgramCrosswalkEntry as ProvisionProgramCrosswalkEntry,
    )
    from polisyos.lex.interventions import (
        HierarchicalPolicySearchPlan as HierarchicalPolicySearchPlan,
    )
    from polisyos.lex.interventions import (
        InterventionKnobSpec as InterventionKnobSpec,
    )
    from polisyos.lex.interventions import (
        LexInterventionCompiler as LexInterventionCompiler,
    )
    from polisyos.lex.interventions import (
        LexProvisionDirective as LexProvisionDirective,
    )
    from polisyos.lex.interventions import (
        StrategicResponseRegistryEntry as StrategicResponseRegistryEntry,
    )
    from polisyos.lex.interventions import (
        StrategicResponseSpecRegistry as StrategicResponseSpecRegistry,
    )
    from polisyos.lex.interventions import (
        TemporalInterventionSequencer as TemporalInterventionSequencer,
    )
    from polisyos.lex.interventions import (
        TemporalInterventionStepInput as TemporalInterventionStepInput,
    )
    from polisyos.lex.knowledge.benchmark import (
        LexBenchmarkOutcome as LexBenchmarkOutcome,
    )
    from polisyos.lex.knowledge.benchmark import (
        run_legal_benchmark as run_legal_benchmark,
    )
    from polisyos.lex.knowledge.search import (
        LegalKnowledgeGraph as LegalKnowledgeGraph,
    )
    from polisyos.lex.legal_evaluation.transport_constraints import (
        ConstraintSeverity as ConstraintSeverity,
    )
    from polisyos.lex.legal_evaluation.transport_constraints import (
        LegalConstraint as LegalConstraint,
    )
    from polisyos.lex.legal_evaluation.transport_constraints import (
        LegalConstraintBridge as LegalConstraintBridge,
    )
    from polisyos.lex.legal_evaluation.transport_constraints import (
        LegalConstraintSet as LegalConstraintSet,
    )
    from polisyos.lex.legal_evaluation.transport_constraints import (
        LegalToDAGMapping as LegalToDAGMapping,
    )
    from polisyos.lex.legal_evaluation.transport_constraints import (
        LegalToDAGMappingType as LegalToDAGMappingType,
    )
    from polisyos.lex.legal_evaluation.transport_constraints import (
        is_transport_blocked as is_transport_blocked,
    )
    from polisyos.lex.normpack import (
        build_legal_authority_report as build_legal_authority_report,
    )
    from polisyos.lex.normpack import (
        build_legal_authority_requirement_artifact as build_legal_authority_requirement_artifact,
    )
    from polisyos.lex.normpack.applicability_report import (
        build_normative_applicability_report as build_normative_applicability_report,
    )
    from polisyos.lex.provenance import (
        LexFabricEvidencePath as LexFabricEvidencePath,
    )
    from polisyos.lex.provenance import (
        lex_evidence_from_fabric_decision_data as lex_evidence_from_fabric_decision_data,
    )
    from polisyos.lex.simulator import (
        AffectedKPI as AffectedKPI,
    )
    from polisyos.lex.simulator import (
        ComplianceDelta as ComplianceDelta,
    )
    from polisyos.lex.simulator import (
        ComplianceTransition as ComplianceTransition,
    )
    from polisyos.lex.simulator import (
        MutationIntent as MutationIntent,
    )
    from polisyos.lex.simulator import (
        NormChange as NormChange,
    )
    from polisyos.lex.simulator import (
        NormChangeType as NormChangeType,
    )
    from polisyos.lex.simulator import (
        NormDiff as NormDiff,
    )
    from polisyos.lex.simulator import (
        NormImpactAnalyzer as NormImpactAnalyzer,
    )
    from polisyos.lex.simulator import (
        NormImpactReport as NormImpactReport,
    )
    from polisyos.lex.simulator import (
        NormPackMutator as NormPackMutator,
    )
    from polisyos.lex.simulator import (
        diff_norm_packs as diff_norm_packs,
    )
    from polisyos.lex.types import (
        ActiveVersionResult as ActiveVersionResult,
    )
    from polisyos.lex.types import (
        ActiveVersionStrategy as ActiveVersionStrategy,
    )
    from polisyos.lex.types import (
        NormPackBudgets as NormPackBudgets,
    )
    from polisyos.lex.types import (
        NormPackBuildRequest as NormPackBuildRequest,
    )
    from polisyos.lex.types import (
        NormPackBuildResult as NormPackBuildResult,
    )

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
