"""Stable search facade for candidate generation, funnel evaluation, and VOI routing.

Eager exports cover objective/stage/stopping contracts and registries that are
pure Python and safe to import in planners. Heavy or cyclic surfaces are
lazy-loaded through `__getattr__`: ask/tell adapters, portfolio search helpers,
promotion/readiness artifacts, and VOI schedulers.
"""

from __future__ import annotations

import importlib
from typing import Any

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
from polisyos.scientist.search.actionable_side_information import (
    ActionableSideInformation,
    load_actionable_side_information,
    persist_actionable_side_information,
    resolve_actionable_store,
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
from polisyos.scientist.search.registry_contracts import (
    BenchmarkRegistryContract,
    ChampionRegistryContract,
    DiscoveryHypothesisRegistryContract,
    LessonRegistryContract,
    ParetoRegistryContract,
)
from polisyos.scientist.search.transfer_context import (
    TransferAuditHop,
    TransferContext,
    TransferPolicy,
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

__all__ = [
    "BenchmarkRegistry",
    "BenchmarkRegistryEntry",
    "BenchmarkRegistrySnapshot",
    "CandidateProposal",
    "EvaluationBundle",
    "OrchestratorFunnelService",
    "SearchService",
    "TellResult",
    "BaseObjective",
    "BudgetDeficitObjective",
    "CompositeObjective",
    "EmploymentObjective",
    "GDPGrowthObjective",
    "InequalityObjective",
    "ObjectivePresets",
    "ObjectiveValue",
    "OptimizationDirection",
    "CheapStage",
    "CorrelationRecord",
    "CorrelationRecordSnapshot",
    "CorrelationTracker",
    "CorrelationTrackerSnapshot",
    "DriftAlert",
    "ExpensiveStage",
    "SearchStage",
    "StageResult",
    "CompositeStoppingCriterion",
    "ImprovementPlateau",
    "MaxIterations",
    "MaxWallTime",
    "StoppingCondition",
    "StoppingCriterion",
    "StoppingPresets",
    "TargetAchieved",
    "NegatedCompositeObjective",
    "ActionableSideInformation",
    "PlatformAttackResult",
    "PlatformMetaEvaluationConfig",
    "PlatformMetaEvaluationInput",
    "PlatformMetaEvaluationReport",
    "PlatformMetaEvaluator",
    "VulnerabilityFound",
    "load_platform_meta_evaluation_report",
    "load_actionable_side_information",
    "persist_platform_meta_evaluation_report",
    "persist_actionable_side_information",
    "resolve_actionable_store",
    "run_stress_test",
    "SensitivityAwareCandidateGenerator",
    "DiversityTracker",
    "ExclusionListBuilder",
    "enrich_context_with_diversity",
    "LessonCard",
    "LessonIndexEntry",
    "LessonIndexSnapshot",
    "LessonKind",
    "LessonPattern",
    "LessonQuery",
    "LessonRegistry",
    "LessonRegistryContract",
    "LessonTrustLevel",
    "lesson_from_failure_card",
    "load_lesson_card",
    "persist_lesson_card",
    "success_lesson_from_outcome",
    "ComplianceAuditEntry",
    "TransferAuditHop",
    "TransferContext",
    "TransferPolicy",
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
    "PortfolioCombination",
    "PortfolioEvaluationResult",
    "PortfolioSearchMode",
    "PortfolioSearchSpace",
    "PortfolioSweep",
    "PortfolioSweepConfig",
    "PortfolioSweepReport",
    "ComputeEconomicsDecision",
    "ParetoSnapshot",
    "ParetoRegistryContract",
    "PredictiveVOIScheduler",
    "PromotionEvidenceBundle",
    "PromotionObservation",
    "ChampionRegistryContract",
    "BenchmarkRegistryContract",
    "DiscoveryHypothesisRegistryContract",
    "SchedulingDecision",
    "SimpleVOIScheduler",
    "VOIModelSnapshot",
    "VOIModelStatus",
    "VOIObservation",
    "VOITrainingConfig",
    "load_promotion_evidence_bundle",
    "assess_latent_governance",
    "latent_governance_metadata",
    "LatentGovernanceAssessment",
    "persist_promotion_evidence_bundle",
    "scientist_blueprint_compliance_audit",
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
            if name in {
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
        "VOIModelSnapshot",
        "VOIModelStatus",
        "VOIObservation",
        "VOITrainingConfig",
    }:
        module = importlib.import_module("polisyos.scientist.search.voi_scheduler")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
