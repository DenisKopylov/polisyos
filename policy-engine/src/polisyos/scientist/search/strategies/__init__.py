"""Advanced search strategies for sample-efficient policy optimization."""

from __future__ import annotations

from polisyos.scientist.search.strategies.adapter import StrategyAdapter
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
    "AcquisitionType",
    "BaseSearchStrategy",
    "Evaluation",
    "EvaluationStatus",
    "GridSearchStrategy",
    "ParameterBounds",
    "ParameterCodec",
    "ParameterType",
    "PolicyCandidate",
    "RandomSearchStrategy",
    "ResourceArbiter",
    "ResourceMode",
    "ScalarParameterCodec",
    "SearchSpace",
    "SearchStrategy",
    "StrategyAdapter",
    "StrategyState",
    "memory_cleanup",
]

try:  # Optional heavy dependencies (torch, botorch, gpytorch)
    from polisyos.scientist.search.strategies.bayesian import (
        BayesianConfig,
        BayesianOptimizer,
    )

    __all__.extend(["BayesianConfig", "BayesianOptimizer"])
except Exception:  # pragma: no cover - optional dependency path
    pass

try:  # Optional heavy dependencies (torch, botorch, gpytorch)
    from polisyos.scientist.search.strategies.multi_objective import (
        MOBayesianOptimizer,
        MOConfig,
    )

    __all__.extend(["MOConfig", "MOBayesianOptimizer"])
except Exception:  # pragma: no cover - optional dependency path
    pass
