"""Stable search facade for candidate generation, funnel evaluation, and VOI routing.

Eager exports cover objective/stage/stopping contracts and registries that are
pure Python and safe to import in planners. Heavy or cyclic surfaces are
lazy-loaded through `__getattr__`: ask/tell adapters, portfolio search helpers,
promotion/readiness artifacts, and VOI schedulers.
"""

from __future__ import annotations

import importlib
from typing import Any

from polisyos.scientist.search.actionable_side_information import (
    ActionableSideInformation,
    load_actionable_side_information,
    persist_actionable_side_information,
    resolve_actionable_store,
)
from polisyos.scientist.search.adversarial import (
    NegatedCompositeObjective,
    PlatformAttackResult,
    PlatformMetaEvaluationConfig,
    PlatformMetaEvaluationInput,
    PlatformMetaEvaluationReport,
    PlatformMetaEvaluator,
    VulnerabilityFound,
    load_platform_meta_evaluation_report,
    persist_platform_meta_evaluation_report,
    run_stress_test,
)
from polisyos.scientist.search.benchmark_registry import (
    BenchmarkRegistry,
    BenchmarkRegistryEntry,
    BenchmarkRegistrySnapshot,
)
from polisyos.scientist.search.compliance_audit import (
    ComplianceAuditEntry,
    scientist_blueprint_compliance_audit,
)
from polisyos.scientist.search.diversity import (
    DiversityTracker,
    ExclusionListBuilder,
    enrich_context_with_diversity,
)
from polisyos.scientist.search.lessons import (
    LessonCard,
    LessonIndexEntry,
    LessonIndexSnapshot,
    LessonKind,
    LessonPattern,
    LessonQuery,
    LessonRegistry,
    LessonTrustLevel,
    lesson_from_failure_card,
    load_lesson_card,
    persist_lesson_card,
    success_lesson_from_outcome,
)
from polisyos.scientist.search.objective import (
    BaseObjective,
    BudgetDeficitObjective,
    CompositeObjective,
    EmploymentObjective,
    GDPGrowthObjective,
    InequalityObjective,
    ObjectivePresets,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.search.registry_contracts import (
    BenchmarkRegistryContract,
    ChampionRegistryContract,
    DiscoveryHypothesisRegistryContract,
    LessonRegistryContract,
    ParetoRegistryContract,
)
from polisyos.scientist.search.sensitivity_adapter import SensitivityAwareCandidateGenerator
from polisyos.scientist.search.sentinels import (
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
from polisyos.scientist.search.stages import (
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
from polisyos.scientist.search.stopping import (
    CompositeStoppingCriterion,
    ImprovementPlateau,
    MaxIterations,
    MaxWallTime,
    StoppingCondition,
    StoppingCriterion,
    StoppingPresets,
    TargetAchieved,
)
from polisyos.scientist.search.transfer_context import (
    TransferAuditHop,
    TransferContext,
    TransferPolicy,
)

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

try:
    from polisyos.scientist.search.cold_start import (
        BurnInCohort,
        BurnInConfig,
        BurnInRunReport,
        build_default_burn_in_orchestrator,
        load_burn_in_report,
        persist_burn_in_report,
        run_burn_in,
    )

    __all__.extend(
        [
            "BurnInCohort",
            "BurnInConfig",
            "BurnInRunReport",
            "build_default_burn_in_orchestrator",
            "load_burn_in_report",
            "persist_burn_in_report",
            "run_burn_in",
        ]
    )
except Exception:  # pragma: no cover - import guard for package init cycles
    pass

try:
    from polisyos.scientist.search.calibration_report import (
        AcceptanceCriterionStatus,
        FunnelCalibrationReport,
        build_calibration_report,
        load_funnel_calibration_report,
        persist_funnel_calibration_report,
        render_calibration_report,
    )

    __all__.extend(
        [
            "AcceptanceCriterionStatus",
            "FunnelCalibrationReport",
            "build_calibration_report",
            "load_funnel_calibration_report",
            "persist_funnel_calibration_report",
            "render_calibration_report",
        ]
    )
except Exception:  # pragma: no cover - import guard for package init cycles
    pass

try:
    from polisyos.scientist.search.strategies import (
        AcquisitionType,
        BaseSearchStrategy,
        Evaluation,
        EvaluationStatus,
        GridSearchStrategy,
        ParameterBounds,
        ParameterType,
        PolicyCandidate,
        RandomSearchStrategy,
        ScalarParameterCodec,
        SearchSpace,
        StrategyAdapter,
        StrategyState,
    )

    __all__.extend(
        [
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
except Exception:  # pragma: no cover - optional dependency path
    pass


def __getattr__(name: str) -> Any:
    """Resolve heavy or cyclic search exports lazily from their owning modules."""
    if name in {
        "CandidateProposal",
        "EvaluationBundle",
        "OrchestratorFunnelService",
        "SearchService",
        "TellResult",
    }:
        module = importlib.import_module("polisyos.scientist.search.contracts")
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
        module = importlib.import_module("polisyos.scientist.search.portfolio")
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
            "polisyos.scientist.search.promotion_evidence"
            if name
            in {
                "PromotionEvidenceBundle",
                "load_promotion_evidence_bundle",
                "persist_promotion_evidence_bundle",
            }
            else "polisyos.scientist.search.latent_governance"
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
            "polisyos.scientist.search.voi_models"
            if name in {"VOIDecisionRecord", "VOIDecisionType", "VOIRunReport"}
            else "polisyos.scientist.search.voi_scheduler"
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
        module = importlib.import_module("polisyos.scientist.search.sbi_scheduler")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
