"""Search loop framework for iterative policy optimization."""

from __future__ import annotations

from polisyos.scientist.search.controller import (
    BatchCandidateGenerator,
    SearchConfig,
    SearchController,
    SearchIteration,
    SearchResult,
    SearchStatus,
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
from polisyos.scientist.search.stages import (
    CheapStage,
    CorrelationRecord,
    CorrelationTracker,
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
    "SearchConfig",
    "SearchController",
    "SearchIteration",
    "SearchResult",
    "SearchStatus",
    "BatchCandidateGenerator",
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
    "CorrelationTracker",
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
]

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
