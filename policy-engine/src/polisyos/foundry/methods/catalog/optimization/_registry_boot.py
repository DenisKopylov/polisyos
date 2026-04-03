"""Public optimization registry boot module API."""
from __future__ import annotations

from typing import Sequence

from .advanced_stochastic import BilevelOptimizationEstimator, ChanceConstrainedEstimator
from .combinatorial import KnapsackEstimator, VehicleRoutingEstimator
from .convex import QuadraticProgramEstimator, RobustOptimizationEstimator
from .game_theory import NashEquilibriumEstimator
from .io_model import LeontiefInputOutput
from .lp import ResourceLP
from .milp import BudgetMILP
from .multiobjective import MultiObjectiveNSGA2Estimator
from .sequential import (
    DynamicProgrammingEstimator,
    SecondOrderConeProgramEstimator,
    TwoStageStochasticProgramEstimator,
)


def register_optimization_methods() -> Sequence[type]:
    """Register optimization methods."""
    return (
        BudgetMILP,
        ResourceLP,
        LeontiefInputOutput,
        QuadraticProgramEstimator,
        RobustOptimizationEstimator,
        MultiObjectiveNSGA2Estimator,
        SecondOrderConeProgramEstimator,
        TwoStageStochasticProgramEstimator,
        DynamicProgrammingEstimator,
        KnapsackEstimator,
        VehicleRoutingEstimator,
        NashEquilibriumEstimator,
        BilevelOptimizationEstimator,
        ChanceConstrainedEstimator,
    )


__all__ = ["register_optimization_methods"]
