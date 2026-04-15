"""Public optimization milp module API."""
from __future__ import annotations

import time
from typing import Any, ClassVar, Mapping

from polisyos.common.logger import get_logger
from polisyos.foundry.methods.backends.protocol import SolverStatus
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .protocols import (
    OptimizationProblem,
    OptimizationResult,
    emit_optimization_metrics,
    parse_optimization_problem,
)

logger = get_logger(__name__)

_ORTOOLS_AVAILABLE: bool | None = None


def _check_ortools() -> bool:
    global _ORTOOLS_AVAILABLE
    if _ORTOOLS_AVAILABLE is None:
        try:
            from ortools.linear_solver import pywraplp  # noqa: F401

            _ORTOOLS_AVAILABLE = True
        except Exception:
            _ORTOOLS_AVAILABLE = False
    return _ORTOOLS_AVAILABLE


def _constraint_ok(lhs: float, sense: str, rhs: float, eps: float = 1e-9) -> bool:
    if sense == "<=":
        return lhs <= rhs + eps
    if sense == ">=":
        return lhs >= rhs - eps
    return abs(lhs - rhs) <= eps


@foundry_method(
    namespace="optimization.integer",
    version="1.0.0",
    tags={"optimization", "milp", "solver"},
)
class BudgetMILP:
    """Knapsack-style budget allocation via Mixed Integer Linear Programming."""

    runtime_stack: ClassVar[tuple[str, ...]] = ("ortools",)
    required_deps: ClassVar[tuple[str, ...]] = ("ortools",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="budget_milp",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="optimization_problem",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("problem", "json"),
                    contract_id=OptimizationProblem.contract_id,
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("result", "json"),
                    contract_id=OptimizationResult.contract_id,
                ),
                SlotSpec(
                    name="solver_info",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("solver", "json"),
                )
            }
        ),
        parameters=(
            ParameterSpec(name="solver_id", default="SCIP"),
            ParameterSpec(name="time_limit_seconds", default=60.0),
            ParameterSpec(name="relative_gap", default=0.01),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Budget allocation using MILP with optional integer variables.",
        tags=frozenset({"optimization", "milp", "solver"}),
        equations={
            "objective": "max sum_i benefit_i * x_i",
            "budget": "sum_i cost_i * x_i <= B",
        },
        when_to_use="Integer/binary decisions (facility location, portfolio, assignment); combinatorial policy design",
        when_not_to_use="Continuous relaxation acceptable; very large problem that can't be solved in time budget",
        output_interpretation="Optimal integer solution + objective. Duality gap = distance from LP relaxation bound. MIP gap % reported.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        problem = parse_optimization_problem(state)
        time_limit_seconds = float(params.get("time_limit_seconds", 60.0))
        relative_gap = max(0.0, float(params.get("relative_gap", 0.01)))
        solver_id = str(params.get("solver_id", "SCIP"))

        result, solver_info = BudgetMILP._solve(
            problem,
            time_limit_seconds=time_limit_seconds,
            relative_gap=relative_gap,
            solver_id=solver_id,
        )
        emit_optimization_metrics(
            method="budget_milp",
            status=result.status,
            duration_seconds=result.solver_time_seconds,
        )
        return result.to_payload(), solver_info

    @staticmethod
    def _solve(
        problem: OptimizationProblem,
        *,
        time_limit_seconds: float,
        relative_gap: float,
        solver_id: str,
    ) -> tuple[OptimizationResult, dict[str, Any]]:
        if not _check_ortools():
            result = OptimizationResult(
                status=SolverStatus.ERROR,
                objective_value=None,
                variables={},
                constraints_satisfied={},
                solver_iterations=0,
                solver_gap=None,
                solver_time_seconds=0.0,
                metadata={"error": "ortools not installed; install policy-engine[solvers]"},
            )
            return result, {"status": result.status.value, "error": result.metadata["error"]}

        from ortools.linear_solver import pywraplp


        t0 = time.perf_counter()
        solver = pywraplp.Solver.CreateSolver(solver_id)
        if solver is None:
            result = OptimizationResult(
                status=SolverStatus.ERROR,
                objective_value=None,
                variables={},
                constraints_satisfied={},
                solver_iterations=0,
                solver_gap=None,
                solver_time_seconds=0.0,
                metadata={"error": f"solver backend '{solver_id}' unavailable"},
            )
            return result, {"status": result.status.value, "error": result.metadata["error"]}

        solver.SetTimeLimit(int(max(0.0, time_limit_seconds) * 1000))
        if relative_gap > 0:
            try:
                solver.SetSolverSpecificParametersAsString(f"limits/gap={relative_gap}")
            except Exception as exc:
                logger.debug("Ignored exception: %s", exc)

        variables: dict[str, Any] = {}
        for item in problem.items:
            if item.is_integer:
                variables[item.item_id] = solver.IntVar(
                    item.min_units,
                    item.max_units,
                    item.item_id,
                )
            else:
                variables[item.item_id] = solver.NumVar(
                    item.min_units,
                    item.max_units,
                    item.item_id,
                )

        objective = solver.Objective()
        for item in problem.items:
            objective.SetCoefficient(variables[item.item_id], float(item.benefit))
        if problem.objective == "maximize":
            objective.SetMaximization()
        else:
            objective.SetMinimization()

        if problem.budget is not None:
            budget_ct = solver.Constraint(-solver.infinity(), float(problem.budget), "budget")
            for item in problem.items:
                budget_ct.SetCoefficient(variables[item.item_id], float(item.cost))

        for constraint in problem.constraints:
            if constraint.sense == "<=":
                ct = solver.Constraint(
                    -solver.infinity(),
                    float(constraint.bound),
                    constraint.constraint_id,
                )
            elif constraint.sense == ">=":
                ct = solver.Constraint(
                    float(constraint.bound),
                    solver.infinity(),
                    constraint.constraint_id,
                )
            else:
                ct = solver.Constraint(
                    float(constraint.bound),
                    float(constraint.bound),
                    constraint.constraint_id,
                )
            for item_id, coefficient in constraint.coefficients.items():
                ct.SetCoefficient(variables[item_id], float(coefficient))

        status_code = solver.Solve()
        elapsed = time.perf_counter() - t0

        status_map = {
            pywraplp.Solver.OPTIMAL: SolverStatus.OPTIMAL,
            pywraplp.Solver.FEASIBLE: SolverStatus.FEASIBLE,
            pywraplp.Solver.INFEASIBLE: SolverStatus.INFEASIBLE,
            pywraplp.Solver.UNBOUNDED: SolverStatus.UNBOUNDED,
            pywraplp.Solver.NOT_SOLVED: SolverStatus.TIMEOUT,
            pywraplp.Solver.ABNORMAL: SolverStatus.ERROR,
        }
        status = status_map.get(status_code, SolverStatus.UNKNOWN)

        solved_values: dict[str, float] = {}
        constraints_ok: dict[str, bool] = {}
        objective_value: float | None = None
        gap: float | None = None
        best_bound: float | None = None

        if status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
            objective_value = float(solver.Objective().Value())
            solved_values = {name: float(var.solution_value()) for name, var in variables.items()}

            if problem.budget is not None:
                spent = sum(item.cost * solved_values[item.item_id] for item in problem.items)
                constraints_ok["budget"] = spent <= float(problem.budget) + 1e-9

            for constraint in problem.constraints:
                lhs = 0.0
                for item_id, coefficient in constraint.coefficients.items():
                    lhs += float(coefficient) * solved_values[item_id]
                constraints_ok[constraint.constraint_id] = _constraint_ok(
                    lhs,
                    constraint.sense,
                    float(constraint.bound),
                )

            obj = solver.Objective()
            if hasattr(obj, "BestBound"):
                try:
                    best_bound = float(obj.BestBound())
                except Exception:
                    best_bound = None

            if status is SolverStatus.OPTIMAL:
                gap = 0.0
            elif best_bound is not None and objective_value is not None:
                denom = max(abs(objective_value), 1e-12)
                gap = abs(objective_value - best_bound) / denom

        uncertainty: UncertaintyEnvelope | None = None
        if objective_value is not None:
            lo = objective_value
            hi = objective_value
            if best_bound is not None:
                lo = min(lo, best_bound)
                hi = max(hi, best_bound)
            uncertainty = UncertaintyEnvelope(
                point_estimate=objective_value,
                confidence_interval=(lo, hi),
                confidence_level=None,
                source=UncertaintySource.CALIBRATION,
                propagation_method=PropagationMethod.NONE,
                interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
                is_heuristic_ci=False,
                gate_eligible=True,
                metadata={
                    "solver_id": solver_id,
                    "method": "budget_milp",
                    "relative_gap_target": relative_gap,
                },
            )

        result = OptimizationResult(
            status=status,
            objective_value=objective_value,
            variables=solved_values,
            constraints_satisfied=constraints_ok,
            solver_iterations=int(getattr(solver, "iterations", lambda: 0)()),
            solver_gap=gap,
            solver_time_seconds=elapsed,
            uncertainty=uncertainty,
            metadata={
                "solver_id": solver_id,
                "num_variables": len(variables),
                "num_constraints": len(problem.constraints)
                + (1 if problem.budget is not None else 0),
                "wall_time_ms": int(getattr(solver, "wall_time", lambda: 0)()),
            },
        )

        solver_info = {
            "status": result.status.value,
            "gap": result.solver_gap,
            "iterations": result.solver_iterations,
            "objective_value": result.objective_value,
        }
        return result, solver_info

__all__ = ["BudgetMILP"]
