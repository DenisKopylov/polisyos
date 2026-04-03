"""Public optimization lp module API."""
from __future__ import annotations

import time
from typing import Any, ClassVar, Mapping

import numpy as np

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


def _check_ortools_available() -> bool:
    try:
        from ortools.linear_solver import pywraplp  # noqa: F401

        return True
    except Exception:
        return False


def _check_scipy_available() -> bool:
    try:
        from scipy.optimize import linprog  # noqa: F401

        return True
    except Exception:
        return False


def _constraint_ok(lhs: float, sense: str, rhs: float, eps: float = 1e-9) -> bool:
    if sense == "<=":
        return lhs <= rhs + eps
    if sense == ">=":
        return lhs >= rhs - eps
    return abs(lhs - rhs) <= eps


@foundry_method(
    namespace="optimization.linear",
    version="1.0.0",
    tags={"optimization", "lp", "solver"},
)
class ResourceLP:
    """Linear programming resource allocation with OR-Tools/Scipy fallback."""

    runtime_stack: ClassVar[tuple[str, ...]] = ("ortools", "scipy", "numpy")
    required_deps: ClassVar[tuple[str, ...]] = ("numpy",)
    optional_deps: ClassVar[tuple[str, ...]] = ("ortools", "scipy")
    fallback_policy: ClassVar[str] = "prefer_ortools_then_scipy"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="resource_lp",
        namespace="placeholder",
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
            ParameterSpec(name="time_limit_seconds", default=30.0),
            ParameterSpec(name="prefer_ortools", default=True),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Linear programming resource allocation with deterministic solvers.",
        tags=frozenset({"optimization", "lp", "solver"}),
        equations={
            "objective": "max c^T x",
            "constraints": "A x <= b, x >= 0",
        },
        when_to_use="Resource allocation with linear objective and constraints; budget optimization; staffing",
        when_not_to_use="Non-convex objective; integer/binary decisions required; nonlinear constraints",
        output_interpretation="Optimal variable values + objective value. Shadow prices (dual values) = marginal value of each constraint.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        problem = parse_optimization_problem(state)
        prefer_ortools = bool(params.get("prefer_ortools", True))
        time_limit_seconds = float(params.get("time_limit_seconds", 30.0))

        result, solver_info = ResourceLP._solve(
            problem,
            prefer_ortools=prefer_ortools,
            time_limit_seconds=time_limit_seconds,
        )
        emit_optimization_metrics(
            method="resource_lp",
            status=result.status,
            duration_seconds=result.solver_time_seconds,
        )
        return result.to_payload(), solver_info

    @staticmethod
    def _solve(
        problem: OptimizationProblem,
        *,
        prefer_ortools: bool,
        time_limit_seconds: float,
    ) -> tuple[OptimizationResult, dict[str, Any]]:
        if prefer_ortools and _check_ortools_available():
            result = ResourceLP._solve_ortools(problem, time_limit_seconds=time_limit_seconds)
        elif _check_scipy_available():
            result = ResourceLP._solve_scipy(problem)
        elif _check_ortools_available():
            result = ResourceLP._solve_ortools(problem, time_limit_seconds=time_limit_seconds)
        else:
            result = OptimizationResult(
                status=SolverStatus.ERROR,
                objective_value=None,
                variables={},
                constraints_satisfied={},
                solver_iterations=0,
                solver_gap=None,
                solver_time_seconds=0.0,
                metadata={"error": "Neither ortools nor scipy is available"},
            )

        solver_info = {
            "status": result.status.value,
            "gap": result.solver_gap,
            "iterations": result.solver_iterations,
            "objective_value": result.objective_value,
        }
        if "backend" in result.metadata:
            solver_info["backend"] = result.metadata["backend"]
        if "error" in result.metadata:
            solver_info["error"] = result.metadata["error"]
        return result, solver_info

    @staticmethod
    def _solve_scipy(problem: OptimizationProblem) -> OptimizationResult:
        from scipy.optimize import linprog

        t0 = time.perf_counter()
        item_ids = [item.item_id for item in problem.items]

        c = np.array([float(item.benefit) for item in problem.items], dtype=float)
        if problem.objective == "maximize":
            c = -c

        bounds = [(float(item.min_units), float(item.max_units)) for item in problem.items]

        a_ub_rows: list[list[float]] = []
        b_ub: list[float] = []
        a_eq_rows: list[list[float]] = []
        b_eq: list[float] = []

        if problem.budget is not None:
            a_ub_rows.append([float(item.cost) for item in problem.items])
            b_ub.append(float(problem.budget))

        for constraint in problem.constraints:
            row = [float(constraint.coefficients.get(item_id, 0.0)) for item_id in item_ids]
            if constraint.sense == "<=":
                a_ub_rows.append(row)
                b_ub.append(float(constraint.bound))
            elif constraint.sense == ">=":
                a_ub_rows.append([-v for v in row])
                b_ub.append(-float(constraint.bound))
            else:
                a_eq_rows.append(row)
                b_eq.append(float(constraint.bound))

        result = linprog(
            c,
            A_ub=np.array(a_ub_rows) if a_ub_rows else None,
            b_ub=np.array(b_ub) if b_ub else None,
            A_eq=np.array(a_eq_rows) if a_eq_rows else None,
            b_eq=np.array(b_eq) if b_eq else None,
            bounds=bounds,
            method="highs",
        )
        elapsed = time.perf_counter() - t0

        status_map = {
            0: SolverStatus.OPTIMAL,
            1: SolverStatus.TIMEOUT,
            2: SolverStatus.INFEASIBLE,
            3: SolverStatus.UNBOUNDED,
            4: SolverStatus.ERROR,
        }
        status = status_map.get(int(result.status), SolverStatus.UNKNOWN)

        objective_value: float | None = None
        solved_values: dict[str, float] = {}
        constraints_ok: dict[str, bool] = {}

        if status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE} and result.x is not None:
            objective_value = float(-result.fun if problem.objective == "maximize" else result.fun)
            solved_values = {
                item_id: float(value) for item_id, value in zip(item_ids, result.x.tolist())
            }
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

        uncertainty: UncertaintyEnvelope | None = None
        if objective_value is not None:
            uncertainty = UncertaintyEnvelope(
                point_estimate=objective_value,
                confidence_interval=(objective_value, objective_value),
                confidence_level=None,
                source=UncertaintySource.CALIBRATION,
                propagation_method=PropagationMethod.NONE,
                interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
                is_heuristic_ci=False,
                gate_eligible=True,
                metadata={"solver": "scipy.optimize.linprog", "method": "resource_lp"},
            )

        return OptimizationResult(
            status=status,
            objective_value=objective_value,
            variables=solved_values,
            constraints_satisfied=constraints_ok,
            solver_iterations=int(getattr(result, "nit", 0) or 0),
            solver_gap=None,
            solver_time_seconds=elapsed,
            uncertainty=uncertainty,
            metadata={"backend": "scipy", "message": str(getattr(result, "message", ""))},
        )

    @staticmethod
    def _solve_ortools(
        problem: OptimizationProblem,
        *,
        time_limit_seconds: float,
    ) -> OptimizationResult:
        from ortools.linear_solver import pywraplp

        t0 = time.perf_counter()
        solver = pywraplp.Solver.CreateSolver("GLOP")
        if solver is None:
            return OptimizationResult(
                status=SolverStatus.ERROR,
                objective_value=None,
                variables={},
                constraints_satisfied={},
                solver_iterations=0,
                solver_gap=None,
                solver_time_seconds=0.0,
                metadata={"backend": "ortools_glop", "error": "GLOP unavailable"},
            )

        solver.SetTimeLimit(int(max(0.0, time_limit_seconds) * 1000))

        variables: dict[str, Any] = {}
        for item in problem.items:
            variables[item.item_id] = solver.NumVar(item.min_units, item.max_units, item.item_id)

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

        objective_value: float | None = None
        solved_values: dict[str, float] = {}
        constraints_ok: dict[str, bool] = {}

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

        uncertainty: UncertaintyEnvelope | None = None
        if objective_value is not None:
            uncertainty = UncertaintyEnvelope(
                point_estimate=objective_value,
                confidence_interval=(objective_value, objective_value),
                confidence_level=None,
                source=UncertaintySource.CALIBRATION,
                propagation_method=PropagationMethod.NONE,
                interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
                is_heuristic_ci=False,
                gate_eligible=True,
                metadata={"solver": "GLOP", "method": "resource_lp"},
            )

        return OptimizationResult(
            status=status,
            objective_value=objective_value,
            variables=solved_values,
            constraints_satisfied=constraints_ok,
            solver_iterations=int(getattr(solver, "iterations", lambda: 0)()),
            solver_gap=None,
            solver_time_seconds=elapsed,
            uncertainty=uncertainty,
            metadata={
                "backend": "ortools_glop",
                "wall_time_ms": int(getattr(solver, "wall_time", lambda: 0)()),
            },
        )

__all__ = ["ResourceLP"]
