from __future__ import annotations

from typing import Sequence

from .convex import QuadraticProgramEstimator, RobustOptimizationEstimator
from .io_model import InputOutputLeontiefModel, LeontiefInputOutput
from .lp import LinearResourceLP, ResourceLP
from .milp import BudgetMILP, IntegerBudgetMILP
from .multiobjective import MultiObjectiveNSGA2Estimator
from .sequential import (
    DynamicProgrammingEstimator,
    SecondOrderConeProgramEstimator,
    TwoStageStochasticProgramEstimator,
)


def register_optimization_methods() -> Sequence[type]:
    return (
        BudgetMILP,
        IntegerBudgetMILP,
        ResourceLP,
        LinearResourceLP,
        LeontiefInputOutput,
        InputOutputLeontiefModel,
        QuadraticProgramEstimator,
        RobustOptimizationEstimator,
        MultiObjectiveNSGA2Estimator,
        SecondOrderConeProgramEstimator,
        TwoStageStochasticProgramEstimator,
        DynamicProgrammingEstimator,
    )


__all__ = ["register_optimization_methods"]
