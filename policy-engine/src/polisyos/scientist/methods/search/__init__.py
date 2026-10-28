"""Stable search facade for candidate generation, funnel evaluation, and VOI routing.

Eager exports cover objective/stage/stopping contracts and registries that are
pure Python and safe to import in planners. Heavy or cyclic surfaces are
lazy-loaded through `__getattr__`: adversarial evaluation, controller/funnel adapters, burn-in and
calibration reports, strategies, portfolio helpers, promotion/readiness artifacts, and VOI schedulers.
"""

from __future__ import annotations

import importlib
from typing import Any

from polisyos.scientist.methods.search.actionable_side_information import (
    ActionableSideInformation,
    load_actionable_side_information,
    persist_actionable_side_information,
    resolve_actionable_store,
)
from polisyos.scientist.methods.search.benchmark_registry import (
    BenchmarkRegistry,
    BenchmarkRegistryEntry,
    BenchmarkRegistrySnapshot,
)
from polisyos.scientist.methods.search.compliance_audit import (
    ComplianceAuditEntry,
    scientist_blueprint_compliance_audit,
)
from polisyos.scientist.methods.search.diversity import (
    DiversityTracker,
    ExclusionListBuilder,
    enrich_context_with_diversity,
)
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonIndexEntry,
    LessonIndexSnapshot,
    LessonKind,
    LessonPattern,
    LessonQuery,
    LessonRegistry,
    LessonTransferBundle,
    LessonTrustLevel,
    lesson_from_failure_card,
    load_lesson_card,
    persist_lesson_card,
    success_lesson_from_outcome,
)
from polisyos.scientist.methods.search.objective import (
    BaseObjective,
    BudgetDeficitObjective,
    CompositeObjective,
    EmploymentObjective,
    GDPGrowthObjective,
    InequalityObjective,
    MethodMetricObservation,
    MethodMetricPredicateEvidence,
    MethodMetricSourceUnit,
    ObjectivePresets,
    ObjectiveScoreStatus,
    ObjectiveValue,
    OptimizationDirection,
    SelectedMethodMetricArtifactRef,
)
from polisyos.scientist.methods.search.registry_contracts import (
    BenchmarkRegistryContract,
    ChampionRegistryContract,
    DiscoveryHypothesisRegistryContract,
    LessonRegistryContract,
    ParetoRegistryContract,
)
from polisyos.scientist.methods.search.sentinels import (
    SENTINEL_METADATA_KEY,
    SentinelCandidate,
    SentinelInjector,
    SentinelKind,
    SentinelObservation,
    SentinelSet,
    extract_sentinel_metadata,
    load_sentinel_set,
    persist_sentinel_set,
    strip_internal_candidate_metadata,
)
from polisyos.scientist.methods.search.stages import (
    CheapStage,
    CorrelationRecord,
    CorrelationRecordSnapshot,
    CorrelationTracker,
    CorrelationTrackerSnapshot,
    DriftAlert,
    ExpensiveStage,
    SearchStage,
    StageResult,
)
from polisyos.scientist.methods.search.stopping import (
    CompositeStoppingCriterion,
    ImprovementPlateau,
    MaxIterations,
    MaxWallTime,
    PlateauToleranceProfile,
    StoppingCondition,
    StoppingCriterion,
    StoppingPresets,
    TargetAchieved,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferAuditHop,
    TransferContext,
    TransferPathBinding,
    TransferPolicy,
    TransferScopeRefusal,
    TransferScopeRefusalReason,
    TransferScopeRefusedError,
    TransferSourceScope,
    TransferTenantScopeStatus,
)

_LAZY_EXPORT_MODULES: dict[str, str] = {
    "StressObjectiveDirectionError": "polisyos.scientist.methods.search.adversarial",
    "NegatedCompositeObjective": "polisyos.scientist.methods.search.adversarial",
    "PlatformAttackResult": "polisyos.scientist.methods.search.adversarial",
    "PlatformMetaEvaluationConfig": "polisyos.scientist.methods.search.adversarial",
    "PlatformMetaEvaluationInput": "polisyos.scientist.methods.search.adversarial",
    "PlatformMetaEvaluationReport": "polisyos.scientist.methods.search.adversarial",
    "PlatformMetaEvaluator": "polisyos.scientist.methods.search.adversarial",
    "VulnerabilityFound": "polisyos.scientist.methods.search.adversarial",
    "load_platform_meta_evaluation_report": "polisyos.scientist.methods.search.adversarial",
    "persist_platform_meta_evaluation_report": "polisyos.scientist.methods.search.adversarial",
    "run_stress_test": "polisyos.scientist.methods.search.adversarial",
    "SensitivityAwareCandidateGenerator": "polisyos.scientist.methods.search.sensitivity_adapter",
    "BurnInCohort": "polisyos.scientist.methods.search.cold_start",
    "BurnInConfig": "polisyos.scientist.methods.search.cold_start",
    "BurnInRunReport": "polisyos.scientist.methods.search.cold_start",
    "build_default_burn_in_orchestrator": "polisyos.scientist.methods.search.cold_start",
    "load_burn_in_report": "polisyos.scientist.methods.search.cold_start",
    "persist_burn_in_report": "polisyos.scientist.methods.search.cold_start",
    "run_burn_in": "polisyos.scientist.methods.search.cold_start",
    "AcceptanceCriterionStatus": "polisyos.scientist.methods.search.calibration_report",
    "FunnelCalibrationReport": "polisyos.scientist.methods.search.calibration_report",
    "build_calibration_report": "polisyos.scientist.methods.search.calibration_report",
    "load_funnel_calibration_report": "polisyos.scientist.methods.search.calibration_report",
    "persist_funnel_calibration_report": "polisyos.scientist.methods.search.calibration_report",
    "render_calibration_report": "polisyos.scientist.methods.search.calibration_report",
    "AcquisitionType": "polisyos.scientist.methods.search.strategies",
    "BaseSearchStrategy": "polisyos.scientist.methods.search.strategies",
    "Evaluation": "polisyos.scientist.methods.search.strategies",
    "EvaluationStatus": "polisyos.scientist.methods.search.strategies",
    "GridSearchStrategy": "polisyos.scientist.methods.search.strategies",
    "ParameterBounds": "polisyos.scientist.methods.search.strategies",
    "ParameterType": "polisyos.scientist.methods.search.strategies",
    "PolicyCandidate": "polisyos.scientist.methods.search.strategies",
    "RandomSearchStrategy": "polisyos.scientist.methods.search.strategies",
    "ScalarParameterCodec": "polisyos.scientist.methods.search.strategies",
    "SearchSpace": "polisyos.scientist.methods.search.strategies",
    "StrategyAdapter": "polisyos.scientist.methods.search.strategies",
    "StrategyState": "polisyos.scientist.methods.search.strategies",
}

__all__ = [
    "StressObjectiveDirectionError",
    "SENTINEL_METADATA_KEY",
    "ActionableSideInformation",
    "BaseObjective",
    "BenchmarkRegistry",
    "BenchmarkRegistryContract",
    "BenchmarkRegistryEntry",
    "BenchmarkRegistrySnapshot",
    "BudgetDeficitObjective",
    "CandidateProposal",
    "CandidateStrategyContext",
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
    "PlateauToleranceProfile",
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
    "LessonTransferBundle",
    "MaxIterations",
    "MaxWallTime",
    "NegatedCompositeObjective",
    "ObjectivePresets",
    "MethodMetricObservation",
    "MethodMetricPredicateEvidence",
    "MethodMetricSourceUnit",
    "ObjectiveScoreStatus",
    "SelectedMethodMetricArtifactRef",
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
    "TransferPathBinding",
    "TransferPolicy",
    "TransferTenantScopeStatus",
    "TransferScopeRefusal",
    "TransferScopeRefusalReason",
    "TransferScopeRefusedError",
    "TransferSourceScope",
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

__all__.extend(name for name in _LAZY_EXPORT_MODULES if name not in __all__)


def __getattr__(name: str) -> Any:
    """Resolve heavy or cyclic search exports lazily from their owning modules."""
    module_name = _LAZY_EXPORT_MODULES.get(name)
    if module_name is not None:
        module = importlib.import_module(module_name)
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name in {
        "CandidateProposal",
        "CandidateStrategyContext",
        "EvaluationBundle",
        "OrchestratorFunnelService",
        "SearchService",
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
