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

from .protocols import OptimizationResult


def _mapping_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, Mapping):
        return dict(state)
    raise TypeError("state must be a mapping")


def _solver_status(status: str) -> SolverStatus:
    normalized = str(status).lower()
    if "optimal" in normalized:
        return SolverStatus.OPTIMAL
    if "infeasible" in normalized:
        return SolverStatus.INFEASIBLE
    if "unbounded" in normalized:
        return SolverStatus.UNBOUNDED
    if "limit" in normalized or "timeout" in normalized:
        return SolverStatus.TIMEOUT
    if "error" in normalized:
        return SolverStatus.ERROR
    return SolverStatus.UNKNOWN


def _serialize_result(result: OptimizationResult) -> dict[str, Any]:
    payload = result.to_payload()
    payload["contract_id"] = OptimizationResult.contract_id
    return payload


def _vector(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D array")
    return arr


def _matrix(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2D array")
    return arr


def _extract_bounds(payload: Mapping[str, Any], n_vars: int) -> tuple[np.ndarray, np.ndarray]:
    bounds = payload.get("bounds")
    if bounds is None:
        return np.zeros(n_vars, dtype=float), np.full(n_vars, np.inf, dtype=float)
    arr = np.asarray(bounds, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != n_vars or arr.shape[1] != 2:
        raise ValueError("bounds must have shape (n_vars, 2)")
    return arr[:, 0], arr[:, 1]


def _pick_solver(cp: Any, requested: str, *fallbacks: str) -> Any:
    installed = {str(name).upper() for name in cp.installed_solvers()}
    candidates = (requested, *fallbacks)
    for candidate in candidates:
        candidate_name = str(candidate).upper()
        if candidate_name in installed and hasattr(cp, candidate_name):
            return getattr(cp, candidate_name)
    return None


@foundry_method(
    namespace="optimization.convex",
    version="1.0.0",
    tags={"optimization", "convex", "quadratic-program"},
)
class QuadraticProgramEstimator:
    runtime_stack: ClassVar[tuple[str, ...]] = ("cvxpy", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="quadratic_program",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("objective_vector", SlotType.VECTOR, Unit("objective", "value"), shape=("n_vars",)),
                SlotSpec(
                    "quadratic_matrix",
                    SlotType.MATRIX,
                    Unit("quadratic", "value"),
                    shape=("n_vars", "n_vars"),
                ),
                SlotSpec(
                    "constraint_matrix",
                    SlotType.MATRIX,
                    Unit("constraint", "value"),
                    shape=("n_constraints", "n_vars"),
                ),
                SlotSpec(
                    "constraint_rhs",
                    SlotType.VECTOR,
                    Unit("constraint", "value"),
                    shape=("n_constraints",),
                ),
                SlotSpec("bounds", SlotType.MATRIX, Unit("bound", "value"), shape=("n_vars", 2)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("result", "json"),
                    contract_id=OptimizationResult.contract_id,
                ),
                SlotSpec("solver_info", SlotType.SCALAR, Unit("solver", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="objective", default="maximize"),
            ParameterSpec(name="solver", default="OSQP"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Quadratic program with explicit vectors, matrices, and bounds.",
        tags=frozenset({"optimization", "convex", "quadratic-program"}),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> Mapping[str, Any]:
        payload = _mapping_payload(fallback_state) if isinstance(fallback_state, Mapping) else {}
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        import cvxpy as cp

        payload = _mapping_payload(state)
        c = _vector(payload["objective_vector"], name="objective_vector")
        q = _matrix(payload["quadratic_matrix"], name="quadratic_matrix")
        a = _matrix(payload["constraint_matrix"], name="constraint_matrix")
        b = _vector(payload["constraint_rhs"], name="constraint_rhs")
        if a.shape[0] != b.shape[0] or a.shape[1] != c.shape[0] or q.shape != (c.shape[0], c.shape[0]):
            raise ValueError("objective/constraint/quadratic dimensions are inconsistent")
        lb, ub = _extract_bounds(payload, c.shape[0])

        x = cp.Variable(c.shape[0])
        q_psd = 0.5 * (q + q.T) + 1e-8 * np.eye(q.shape[0], dtype=float)
        objective_name = str(params.get("objective", "maximize")).lower()
        expr = cp.sum(cp.multiply(c, x)) - 0.5 * cp.quad_form(x, q_psd)
        objective = cp.Maximize(expr) if objective_name == "maximize" else cp.Minimize(-expr)
        constraints = [a @ x <= b, x >= lb]
        finite_ub = np.isfinite(ub)
        if finite_ub.any():
            constraints.append(x[finite_ub] <= ub[finite_ub])
        problem = cp.Problem(objective, constraints)

        started = time.perf_counter()
        solver_name = str(params.get("solver", "OSQP")).upper()
        solver = _pick_solver(cp, solver_name, "OSQP", "CLARABEL", "SCS")
        problem.solve(solver=solver, verbose=False)
        elapsed = time.perf_counter() - started

        status = _solver_status(problem.status)
        solution = np.zeros(c.shape[0], dtype=float) if x.value is None else np.asarray(x.value, dtype=float)
        lhs = a @ solution
        constraints_ok = {
            f"constraint_{idx}": bool(lhs[idx] <= b[idx] + 1e-6) for idx in range(a.shape[0])
        }
        constraints_ok["lower_bounds"] = bool(np.all(solution >= lb - 1e-6))
        constraints_ok["upper_bounds"] = bool(np.all(solution[finite_ub] <= ub[finite_ub] + 1e-6))

        result = OptimizationResult(
            status=status,
            objective_value=(None if problem.value is None else float(problem.value)),
            variables={f"x_{idx}": float(solution[idx]) for idx in range(solution.shape[0])},
            constraints_satisfied=constraints_ok,
            solver_iterations=int(getattr(problem.solver_stats, "num_iters", 0) or 0),
            solver_gap=None,
            solver_time_seconds=float(getattr(problem.solver_stats, "solve_time", elapsed) or elapsed),
            metadata={"solver": solver_name, "objective": objective_name},
        )
        solver_info = {
            "status": status.value,
            "gap": None,
            "iterations": result.solver_iterations,
            "objective_value": result.objective_value,
            "solver": solver_name,
        }
        return _serialize_result(result), solver_info


@foundry_method(
    namespace="optimization.convex",
    version="1.0.0",
    tags={"optimization", "convex", "robust-optimization"},
)
class RobustOptimizationEstimator:
    runtime_stack: ClassVar[tuple[str, ...]] = ("cvxpy", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="robust_optimization",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("objective_vector", SlotType.VECTOR, Unit("objective", "value"), shape=("n_vars",)),
                SlotSpec(
                    "constraint_matrix",
                    SlotType.MATRIX,
                    Unit("constraint", "value"),
                    shape=("n_constraints", "n_vars"),
                ),
                SlotSpec(
                    "constraint_rhs",
                    SlotType.VECTOR,
                    Unit("constraint", "value"),
                    shape=("n_constraints",),
                ),
                SlotSpec("bounds", SlotType.MATRIX, Unit("bound", "value"), shape=("n_vars", 2)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("result", "json"),
                    contract_id=OptimizationResult.contract_id,
                ),
                SlotSpec("solver_info", SlotType.SCALAR, Unit("solver", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="uncertainty_radius", default=0.1),
            ParameterSpec(name="solver", default="ECOS"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Robust linear allocation with L1 uncertainty penalty on the objective.",
        tags=frozenset({"optimization", "convex", "robust-optimization"}),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> Mapping[str, Any]:
        payload = _mapping_payload(fallback_state) if isinstance(fallback_state, Mapping) else {}
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        import cvxpy as cp

        payload = _mapping_payload(state)
        c = _vector(payload["objective_vector"], name="objective_vector")
        a = _matrix(payload["constraint_matrix"], name="constraint_matrix")
        b = _vector(payload["constraint_rhs"], name="constraint_rhs")
        if a.shape[0] != b.shape[0] or a.shape[1] != c.shape[0]:
            raise ValueError("objective/constraint dimensions are inconsistent")
        lb, ub = _extract_bounds(payload, c.shape[0])
        rho = max(0.0, float(params.get("uncertainty_radius", 0.1)))

        x = cp.Variable(c.shape[0])
        objective = cp.Maximize(cp.sum(cp.multiply(c, x)) - rho * cp.norm1(x))
        constraints = [a @ x <= b, x >= lb]
        finite_ub = np.isfinite(ub)
        if finite_ub.any():
            constraints.append(x[finite_ub] <= ub[finite_ub])
        problem = cp.Problem(objective, constraints)

        started = time.perf_counter()
        solver_name = str(params.get("solver", "ECOS")).upper()
        solver = _pick_solver(cp, solver_name, "SCS", "CLARABEL", "OSQP")
        problem.solve(solver=solver, verbose=False)
        elapsed = time.perf_counter() - started

        status = _solver_status(problem.status)
        solution = np.zeros(c.shape[0], dtype=float) if x.value is None else np.asarray(x.value, dtype=float)
        lhs = a @ solution
        constraints_ok = {
            f"constraint_{idx}": bool(lhs[idx] <= b[idx] + 1e-6) for idx in range(a.shape[0])
        }
        result = OptimizationResult(
            status=status,
            objective_value=(None if problem.value is None else float(problem.value)),
            variables={f"x_{idx}": float(solution[idx]) for idx in range(solution.shape[0])},
            constraints_satisfied=constraints_ok,
            solver_iterations=int(getattr(problem.solver_stats, "num_iters", 0) or 0),
            solver_gap=None,
            solver_time_seconds=float(getattr(problem.solver_stats, "solve_time", elapsed) or elapsed),
            metadata={"solver": solver_name, "uncertainty_radius": rho},
        )
        solver_info = {
            "status": status.value,
            "gap": None,
            "iterations": result.solver_iterations,
            "objective_value": result.objective_value,
            "solver": solver_name,
        }
        return _serialize_result(result), solver_info


__all__ = [
    "QuadraticProgramEstimator",
    "RobustOptimizationEstimator",
]
