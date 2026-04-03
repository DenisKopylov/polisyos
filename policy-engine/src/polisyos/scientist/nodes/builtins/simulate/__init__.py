"""Public builtins simulate package API."""
from __future__ import annotations

from .run_simulation import RunSimulationNode

try:  # pragma: no cover - optional JAX dependency
    from .propagate_uncertainty import PropagateUncertaintyNode
except ModuleNotFoundError:  # pragma: no cover
    PropagateUncertaintyNode = None  # type: ignore[assignment]

try:  # pragma: no cover - optional JAX dependency
    from .run_distributional_analysis import RunDistributionalAnalysisNode
except ModuleNotFoundError:  # pragma: no cover
    RunDistributionalAnalysisNode = None  # type: ignore[assignment]

try:  # pragma: no cover - optional JAX dependency
    from .run_causal_evaluation import RunCausalEvaluationNode
except ModuleNotFoundError:  # pragma: no cover
    RunCausalEvaluationNode = None  # type: ignore[assignment]

__all__ = [
    "RunSimulationNode",
    "RunCausalEvaluationNode",
    "RunDistributionalAnalysisNode",
    "PropagateUncertaintyNode",
]
