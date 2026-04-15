"""Advanced search strategies for sample-efficient policy optimization."""

from __future__ import annotations

from polisyos.scientist.search.strategies.adapter import StrategyAdapter
from polisyos.scientist.search.strategies.advanced_policy import (
    AdvancedSearchPolicyConfig,
    AdvancedSearchPolicyReport,
    AdvancedSearchPolicyRolloutStatus,
    ASHADecision,
    ASHAScheduler,
    BOHBSampler,
    CMAESExplorer,
    ConstraintPropagationResult,
    ConstraintSpec,
    ExplicitConstraintPropagator,
    GaussianProcessCheapStageSurrogate,
    LearnedRoutingPolicy,
    LearnedVOIPolicy,
    PopulationBasedTrainingScheduler,
    PopulationMember,
    RoutingTrainingExample,
    VOITrainingExample,
    build_advanced_search_policy_report,
)
from polisyos.scientist.search.strategies.base import BaseSearchStrategy, SearchStrategy
from polisyos.scientist.search.strategies.codec import ParameterCodec, ScalarParameterCodec
from polisyos.scientist.search.strategies.grid import GridSearchStrategy
from polisyos.scientist.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.search.strategies.resource_arbiter import (
    ResourceArbiter,
    ResourceMode,
    memory_cleanup,
)
from polisyos.scientist.search.strategies.space import SearchSpace
from polisyos.scientist.search.strategies.types import (
    AcquisitionType,
    Evaluation,
    EvaluationStatus,
    ParameterBounds,
    ParameterType,
    PolicyCandidate,
    StrategyState,
)

__all__ = [
    "ASHADecision",
    "ASHAScheduler",
    "AcquisitionType",
    "AdvancedSearchPolicyConfig",
    "AdvancedSearchPolicyReport",
    "AdvancedSearchPolicyRolloutStatus",
    "BOHBSampler",
    "BaseSearchStrategy",
    "CMAESExplorer",
    "ConstraintPropagationResult",
    "ConstraintSpec",
    "Evaluation",
    "EvaluationStatus",
    "ExplicitConstraintPropagator",
    "GaussianProcessCheapStageSurrogate",
    "GridSearchStrategy",
    "LearnedRoutingPolicy",
    "LearnedVOIPolicy",
    "ParameterBounds",
    "ParameterCodec",
    "ParameterType",
    "PolicyCandidate",
    "PopulationBasedTrainingScheduler",
    "PopulationMember",
    "RandomSearchStrategy",
    "ResourceArbiter",
    "ResourceMode",
    "RoutingTrainingExample",
    "ScalarParameterCodec",
    "SearchSpace",
    "SearchStrategy",
    "StrategyAdapter",
    "StrategyState",
    "VOITrainingExample",
    "build_advanced_search_policy_report",
    "memory_cleanup",
]

_OPTIONAL_IMPORT_ERRORS: dict[str, str] = {}

try:  # Optional heavy dependencies (torch, botorch, gpytorch)
    from polisyos.scientist.search.strategies.bayesian import (
        BayesianConfig as BayesianConfig,
    )
    from polisyos.scientist.search.strategies.bayesian import (
        BayesianOptimizer as BayesianOptimizer,
    )

    __all__.extend(["BayesianConfig", "BayesianOptimizer"])
except Exception as exc:  # pragma: no cover - optional dependency path
    _OPTIONAL_IMPORT_ERRORS["bayesian"] = f"{type(exc).__name__}: {exc}"

try:  # Optional heavy dependencies (torch, botorch, gpytorch)
    from polisyos.scientist.search.strategies.multi_objective import (
        MOBayesianOptimizer as MOBayesianOptimizer,
    )
    from polisyos.scientist.search.strategies.multi_objective import (
        MOConfig as MOConfig,
    )

    __all__.extend(["MOBayesianOptimizer", "MOConfig"])
except Exception as exc:  # pragma: no cover - optional dependency path
    _OPTIONAL_IMPORT_ERRORS["multi_objective"] = f"{type(exc).__name__}: {exc}"
