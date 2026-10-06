"""Lazy search facade over the existing canonical owners.

Contract-only package imports load no controller, funnel or optional numerical
backend. Supported attributes retain identity with their canonical modules;
optional dependencies are resolved when their attributes are requested.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "SENTINEL_METADATA_KEY",
    "ActionableSideInformation",
    "BaseObjective",
    "BenchmarkRegistry",
    "BenchmarkRegistryContract",
    "BenchmarkRegistryEntry",
    "BenchmarkRegistrySnapshot",
    "BudgetDeficitObjective",
    "CandidateProposal",
    "ChampionRegistryContract",
    "CheapStage",
    "ComplianceAuditEntry",
    "CompositeObjective",
    "CompositeStoppingCriterion",
    "ComputeEconomicsDecision",
    "CorrelationRecord",
    "CorrelationRecordSnapshot",
    "CPBASISConfig",
    "CPBASISPlan",
    "CPBASISScore",
    "CorrelationTracker",
    "CorrelationTrackerSnapshot",
    "DiscoveryHypothesisRegistryContract",
    "DiversityTracker",
    "DriftAlert",
    "EmploymentObjective",
    "EvaluationBundle",
    "ExclusionListBuilder",
    "ExpensiveStage",
    "GDPGrowthObjective",
    "ImprovementPlateau",
    "InequalityObjective",
    "LatentGovernanceAssessment",
    "LessonCard",
    "LessonIndexEntry",
    "LessonIndexSnapshot",
    "LessonKind",
    "LessonPattern",
    "LessonQuery",
    "LessonRegistry",
    "LessonRegistryContract",
    "LessonTrustLevel",
    "MaxIterations",
    "MaxWallTime",
    "NegatedCompositeObjective",
    "ObjectivePresets",
    "ObjectiveValue",
    "OptimizationDirection",
    "OrchestratorFunnelService",
    "ParetoRegistryContract",
    "ParetoSnapshot",
    "PlatformAttackResult",
    "PlatformMetaEvaluationConfig",
    "PlatformMetaEvaluationInput",
    "PlatformMetaEvaluationReport",
    "PlatformMetaEvaluator",
    "PortfolioCombination",
    "PortfolioEvaluationResult",
    "PortfolioSearchMode",
    "PortfolioSearchSpace",
    "PortfolioSweep",
    "PortfolioSweepConfig",
    "PortfolioSweepReport",
    "PredictiveVOIScheduler",
    "PromotionEvidenceBundle",
    "PromotionObservation",
    "ProofAwareSBIScheduler",
    "ProofGateReceipt",
    "ProofGateStatus",
    "SchedulingDecision",
    "SearchService",
    "NativeSearchService",
    "SearchServiceCheckpoint",
    "SearchStage",
    "SensitivityAwareCandidateGenerator",
    "SBICalibrationPolicy",
    "SBICalibrationSummary",
    "SBIDesignCandidate",
    "SBIInferenceFamily",
    "SentinelCandidate",
    "SentinelInjector",
    "SentinelKind",
    "SentinelObservation",
    "SentinelSet",
    "SimpleVOIScheduler",
    "StageResult",
    "StoppingCondition",
    "StoppingCriterion",
    "StoppingPresets",
    "TargetAchieved",
    "TellResult",
    "TransferAuditHop",
    "TransferContext",
    "TransferPolicy",
    "VOIModelSnapshot",
    "VOIModelStatus",
    "VOIObservation",
    "VOIRunReport",
    "VOITrainingConfig",
    "VOIDecisionRecord",
    "VOIDecisionType",
    "VulnerabilityFound",
    "assess_latent_governance",
    "build_cp_basis_design_plan",
    "build_adversarial_challenge_voi_decision",
    "build_stop_search_voi_decision",
    "enrich_context_with_diversity",
    "extract_sentinel_metadata",
    "latent_governance_metadata",
    "lesson_from_failure_card",
    "load_actionable_side_information",
    "load_lesson_card",
    "load_platform_meta_evaluation_report",
    "load_promotion_evidence_bundle",
    "load_sentinel_set",
    "persist_actionable_side_information",
    "persist_lesson_card",
    "persist_platform_meta_evaluation_report",
    "persist_promotion_evidence_bundle",
    "persist_sentinel_set",
    "proof_gate_from_bridge",
    "resolve_actionable_store",
    "run_stress_test",
    "scientist_blueprint_compliance_audit",
    "strip_internal_candidate_metadata",
    "success_lesson_from_outcome",
    "build_voi_run_report",
    "load_voi_run_report",
    "persist_voi_run_report",
    "scheduling_decision_to_voi_record",
]


_EXPORT_MODULES: dict[str, tuple[str, ...]] = {
    "polisyos.scientist.methods.search.actionable_side_information": (
        "ActionableSideInformation",
        "load_actionable_side_information",
        "persist_actionable_side_information",
        "resolve_actionable_store",
    ),
    "polisyos.scientist.methods.search.adversarial": (
        "NegatedCompositeObjective",
        "PlatformAttackResult",
        "PlatformMetaEvaluationConfig",
        "PlatformMetaEvaluationInput",
        "PlatformMetaEvaluationReport",
        "PlatformMetaEvaluator",
        "VulnerabilityFound",
        "load_platform_meta_evaluation_report",
        "persist_platform_meta_evaluation_report",
        "run_stress_test",
    ),
    "polisyos.scientist.methods.search.benchmark_registry": (
        "BenchmarkRegistry",
        "BenchmarkRegistryEntry",
        "BenchmarkRegistrySnapshot",
    ),
    "polisyos.scientist.methods.search.compliance_audit": (
        "ComplianceAuditEntry",
        "scientist_blueprint_compliance_audit",
    ),
    "polisyos.scientist.methods.search.diversity": (
        "DiversityTracker",
        "ExclusionListBuilder",
        "enrich_context_with_diversity",
    ),
    "polisyos.scientist.methods.search.lessons": (
        "LessonCard",
        "LessonIndexEntry",
        "LessonIndexSnapshot",
        "LessonKind",
        "LessonPattern",
        "LessonQuery",
        "LessonRegistry",
        "LessonTrustLevel",
        "lesson_from_failure_card",
        "load_lesson_card",
        "persist_lesson_card",
        "success_lesson_from_outcome",
    ),
    "polisyos.scientist.methods.search.objective": (
        "BaseObjective",
        "BudgetDeficitObjective",
        "CompositeObjective",
        "EmploymentObjective",
        "GDPGrowthObjective",
        "InequalityObjective",
        "ObjectivePresets",
        "ObjectiveValue",
        "OptimizationDirection",
    ),
    "polisyos.scientist.methods.search.registry_contracts": (
        "BenchmarkRegistryContract",
        "ChampionRegistryContract",
        "DiscoveryHypothesisRegistryContract",
        "LessonRegistryContract",
        "ParetoRegistryContract",
    ),
    "polisyos.scientist.methods.search.sensitivity_adapter": (
        "SensitivityAwareCandidateGenerator",
    ),
    "polisyos.scientist.methods.search.sentinels": (
        "SENTINEL_METADATA_KEY",
        "SentinelCandidate",
        "SentinelInjector",
        "SentinelKind",
        "SentinelObservation",
        "SentinelSet",
        "extract_sentinel_metadata",
        "load_sentinel_set",
        "persist_sentinel_set",
        "strip_internal_candidate_metadata",
    ),
    "polisyos.scientist.methods.search.stages": (
        "CheapStage",
        "CorrelationRecord",
        "CorrelationRecordSnapshot",
        "CorrelationTracker",
        "CorrelationTrackerSnapshot",
        "DriftAlert",
        "ExpensiveStage",
        "SearchStage",
        "StageResult",
    ),
    "polisyos.scientist.methods.search.stopping": (
        "CompositeStoppingCriterion",
        "ImprovementPlateau",
        "MaxIterations",
        "MaxWallTime",
        "StoppingCondition",
        "StoppingCriterion",
        "StoppingPresets",
        "TargetAchieved",
    ),
    "polisyos.scientist.methods.search.transfer_context": (
        "TransferAuditHop",
        "TransferContext",
        "TransferPolicy",
    ),
    "polisyos.scientist.methods.search.cold_start": (
        "BurnInCohort",
        "BurnInConfig",
        "BurnInRunReport",
        "build_default_burn_in_orchestrator",
        "load_burn_in_report",
        "persist_burn_in_report",
        "run_burn_in",
    ),
    "polisyos.scientist.methods.search.calibration_report": (
        "AcceptanceCriterionStatus",
        "FunnelCalibrationReport",
        "build_calibration_report",
        "load_funnel_calibration_report",
        "persist_funnel_calibration_report",
        "render_calibration_report",
    ),
    "polisyos.scientist.methods.search.strategies": (
        "AcquisitionType",
        "BaseSearchStrategy",
        "Evaluation",
        "EvaluationStatus",
        "GridSearchStrategy",
        "ParameterBounds",
        "ParameterType",
        "PolicyCandidate",
        "RandomSearchStrategy",
        "ScalarParameterCodec",
        "SearchSpace",
        "StrategyAdapter",
        "StrategyState",
    ),
}

_LAZY_EXPORTS = {name: module for module, names in _EXPORT_MODULES.items() for name in names}
__all__.extend(
    [
        "BurnInCohort",
        "BurnInConfig",
        "BurnInRunReport",
        "build_default_burn_in_orchestrator",
        "load_burn_in_report",
        "persist_burn_in_report",
        "run_burn_in",
        "AcceptanceCriterionStatus",
        "FunnelCalibrationReport",
        "build_calibration_report",
        "load_funnel_calibration_report",
        "persist_funnel_calibration_report",
        "render_calibration_report",
        "AcquisitionType",
        "BaseSearchStrategy",
        "Evaluation",
        "EvaluationStatus",
        "GridSearchStrategy",
        "ParameterBounds",
        "ParameterType",
        "PolicyCandidate",
        "RandomSearchStrategy",
        "ScalarParameterCodec",
        "SearchSpace",
        "StrategyAdapter",
        "StrategyState",
    ]
)


def __getattr__(name: str) -> Any:
    """Resolve heavy or cyclic search exports lazily from their owning modules."""
    if name in _LAZY_EXPORTS:
        value = getattr(importlib.import_module(_LAZY_EXPORTS[name]), name)
        globals()[name] = value
        return value
    if name == "NativeSearchService":
        module = importlib.import_module("polisyos.scientist.methods.search.service")
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name in {
        "CandidateProposal",
        "EvaluationBundle",
        "OrchestratorFunnelService",
        "SearchService",
        "SearchServiceCheckpoint",
        "TellResult",
    }:
        module = importlib.import_module("polisyos.scientist.methods.search.contracts")
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name in {
        "PortfolioCombination",
        "PortfolioEvaluationResult",
        "PortfolioSearchMode",
        "PortfolioSearchSpace",
        "PortfolioSweep",
        "PortfolioSweepConfig",
        "PortfolioSweepReport",
    }:
        module = importlib.import_module("polisyos.scientist.methods.search.portfolio")
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name in {
        "PromotionEvidenceBundle",
        "load_promotion_evidence_bundle",
        "persist_promotion_evidence_bundle",
        "LatentGovernanceAssessment",
        "assess_latent_governance",
        "latent_governance_metadata",
    }:
        module_name = (
            "polisyos.scientist.methods.search.promotion_evidence"
            if name
            in {
                "PromotionEvidenceBundle",
                "load_promotion_evidence_bundle",
                "persist_promotion_evidence_bundle",
            }
            else "polisyos.scientist.methods.search.latent_governance"
        )
        module = importlib.import_module(module_name)
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name in {
        "ComputeEconomicsDecision",
        "ParetoSnapshot",
        "PredictiveVOIScheduler",
        "PromotionObservation",
        "SchedulingDecision",
        "SimpleVOIScheduler",
        "VOIDecisionRecord",
        "VOIDecisionType",
        "VOIModelSnapshot",
        "VOIModelStatus",
        "VOIObservation",
        "VOIRunReport",
        "VOITrainingConfig",
        "build_adversarial_challenge_voi_decision",
        "build_stop_search_voi_decision",
        "build_voi_run_report",
        "load_voi_run_report",
        "persist_voi_run_report",
        "scheduling_decision_to_voi_record",
    }:
        module_name = (
            "polisyos.scientist.methods.search.voi_models"
            if name in {"VOIDecisionRecord", "VOIDecisionType", "VOIRunReport"}
            else "polisyos.scientist.methods.search.voi_scheduler"
        )
        module = importlib.import_module(module_name)
        return getattr(module, name)
    if name in {
        "CPBASISConfig",
        "CPBASISPlan",
        "CPBASISScore",
        "ProofAwareSBIScheduler",
        "ProofGateReceipt",
        "ProofGateStatus",
        "SBICalibrationPolicy",
        "SBICalibrationSummary",
        "SBIDesignCandidate",
        "SBIInferenceFamily",
        "build_cp_basis_design_plan",
        "proof_gate_from_bridge",
    }:
        module = importlib.import_module("polisyos.scientist.methods.search.sbi_scheduler")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
