"""Expose optimization methods and register them into the shared Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_optimization_methods
from .advanced_stochastic import (
    BilevelOptimizationEstimator,
    ChanceConstrainedEstimator,
    LegacyBilevelOptimizationEstimator,
    compute_incumbent_objective_bounds,
)
from .auction import PublicReserveAuctionEstimator
from .combinatorial import KnapsackEstimator, VehicleRoutingEstimator
from .convex import (
    QuadraticProgramEstimator,
    RobustOptimizationEstimator,
    SetBasedRobustLinearEstimator,
)
from .game_theory import NashEquilibriumEstimator
from .io_model import LeontiefInputOutput
from .lp import ResourceLP
from .milp import BudgetMILP
from .moment_dro import MomentConstrainedDROEstimator
from .multiobjective import MultiObjectiveNSGA2Estimator
from .protocols import (
    AllocationItem,
    AmbiguityCertificate,
    AuctionFormatRecommendation,
    AuctionReserveProblem,
    ConstraintCertificate,
    DiagnosticResult,
    InputOutputMethod,
    IOModelResult,
    MomentBound,
    MomentDROConstraint,
    MomentDROProblem,
    OptimizationAmbiguityCertificate,
    OptimizationMethod,
    OptimizationProblem,
    OptimizationResult,
    ResourceConstraint,
    parse_auction_reserve_problem,
)
from .sequential import (
    DynamicProgrammingEstimator,
    SecondOrderConeProgramEstimator,
    TwoStageStochasticProgramEstimator,
)


def ensure_optimization_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with optimization methods for planners and catalog snapshots."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_optimization_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "AllocationItem",
    "AmbiguityCertificate",
    "AuctionFormatRecommendation",
    "AuctionReserveProblem",
    "BilevelOptimizationEstimator",
    "BudgetMILP",
    "ChanceConstrainedEstimator",
    "ConstraintCertificate",
    "DiagnosticResult",
    "DynamicProgrammingEstimator",
    "IOModelResult",
    "InputOutputMethod",
    "KnapsackEstimator",
    "LegacyBilevelOptimizationEstimator",
    "LeontiefInputOutput",
    "MomentBound",
    "MomentConstrainedDROEstimator",
    "MomentDROConstraint",
    "MomentDROProblem",
    "MultiObjectiveNSGA2Estimator",
    "NashEquilibriumEstimator",
    "OptimizationAmbiguityCertificate",
    "OptimizationMethod",
    "OptimizationProblem",
    "OptimizationResult",
    "PublicReserveAuctionEstimator",
    "QuadraticProgramEstimator",
    "ResourceConstraint",
    "ResourceLP",
    "RobustOptimizationEstimator",
    "SecondOrderConeProgramEstimator",
    "SetBasedRobustLinearEstimator",
    "TwoStageStochasticProgramEstimator",
    "VehicleRoutingEstimator",
    "compute_incumbent_objective_bounds",
    "ensure_optimization_methods_registered",
    "parse_auction_reserve_problem",
    "register_optimization_methods",
]
