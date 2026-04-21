"""Lazy facade for simulation-stage builtin nodes."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .propagate_uncertainty import PropagateUncertaintyNode
    from .run_causal_evaluation import RunCausalEvaluationNode
    from .run_distributional_analysis import RunDistributionalAnalysisNode
    from .run_metric_validation import RunMetricValidationNode
    from .run_simulation import RunSimulationNode

__all__ = [
    "RunSimulationNode",
    "RunMetricValidationNode",
    "RunCausalEvaluationNode",
    "RunDistributionalAnalysisNode",
    "PropagateUncertaintyNode",
]


def __getattr__(name: str) -> Any:
    if name == "RunSimulationNode":
        from .run_simulation import RunSimulationNode

        return RunSimulationNode
    if name == "RunMetricValidationNode":
        from .run_metric_validation import RunMetricValidationNode

        return RunMetricValidationNode
    if name == "RunCausalEvaluationNode":
        from .run_causal_evaluation import RunCausalEvaluationNode

        return RunCausalEvaluationNode
    if name == "RunDistributionalAnalysisNode":
        from .run_distributional_analysis import RunDistributionalAnalysisNode

        return RunDistributionalAnalysisNode
    if name == "PropagateUncertaintyNode":
        from .propagate_uncertainty import PropagateUncertaintyNode

        return PropagateUncertaintyNode
    raise AttributeError(name)
