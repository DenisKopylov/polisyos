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


def _serialize_result(result: OptimizationResult) -> dict[str, Any]:
    payload = result.to_payload()
    payload["contract_id"] = OptimizationResult.contract_id
    return payload


def _pick_solver(cp: Any, requested: str, *fallbacks: str) -> Any:
    installed = {str(name).upper() for name in cp.installed_solvers()}
    for candidate in (requested, *fallbacks):
        token = str(candidate).upper()
        if token in installed and hasattr(cp, token):
            return getattr(cp, token)
    return None


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


@foundry_method(
    namespace="optimization.convex",
    version="1.0.0",
    tags={"optimization", "convex", "socp"},
)
class SecondOrderConeProgramEstimator:
    runtime_stack: ClassVar[tuple[str, ...]] = ("cvxpy", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="socp",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("objective_vector", SlotType.VECTOR, Unit("objective", "value"), shape=("n_vars",)),
                SlotSpec("cone_matrix", SlotType.MATRIX, Unit("cone", "value"), shape=("n_cone_rows", "n_vars")),
                SlotSpec("cone_bound", SlotType.SCALAR, Unit("cone", "value")),
                SlotSpec(
                    "linear_constraint_matrix",
                    SlotType.MATRIX,
                    Unit("constraint", "value"),
                    shape=("n_constraints", "n_vars"),
                ),
                SlotSpec("linear_constraint_rhs", SlotType.VECTOR, Unit("constraint", "value"), shape=("n_constraints",)),
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
        parameters=(ParameterSpec(name="solver", default="SCS"),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Second-order cone program with one L2 norm cone and linear side constraints.",
        tags=frozenset({"optimization", "convex", "socp"}),
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
        c = np.asarray(payload["objective_vector"], dtype=float)
        cone_matrix = np.asarray(payload["cone_matrix"], dtype=float)
        cone_bound = float(payload["cone_bound"])
        g = np.asarray(payload["linear_constraint_matrix"], dtype=float)
        h = np.asarray(payload["linear_constraint_rhs"], dtype=float)
        bounds = np.asarray(payload["bounds"], dtype=float)

        x = cp.Variable(c.shape[0])
        lb = bounds[:, 0]
        ub = bounds[:, 1]
        objective = cp.Maximize(cp.sum(cp.multiply(c, x)))
        constraints = [cp.norm(cone_matrix @ x, 2) <= cone_bound, g @ x <= h, x >= lb]
        finite_ub = np.isfinite(ub)
        if finite_ub.any():
            constraints.append(x[finite_ub] <= ub[finite_ub])
        problem = cp.Problem(objective, constraints)

        started = time.perf_counter()
        solver_name = str(params.get("solver", "SCS")).upper()
        solver = _pick_solver(cp, solver_name, "SCS", "CLARABEL", "ECOS", "OSQP")
        problem.solve(solver=solver, verbose=False)
        elapsed = time.perf_counter() - started

        status = _solver_status(problem.status)
        solution = np.zeros(c.shape[0], dtype=float) if x.value is None else np.asarray(x.value, dtype=float)
        result = OptimizationResult(
            status=status,
            objective_value=(None if problem.value is None else float(problem.value)),
            variables={f"x_{idx}": float(solution[idx]) for idx in range(solution.shape[0])},
            constraints_satisfied={
                "cone": bool(np.linalg.norm(cone_matrix @ solution) <= cone_bound + 1e-6),
                "linear": bool(np.all(g @ solution <= h + 1e-6)),
            },
            solver_iterations=int(getattr(problem.solver_stats, "num_iters", 0) or 0),
            solver_gap=None,
            solver_time_seconds=float(getattr(problem.solver_stats, "solve_time", elapsed) or elapsed),
            metadata={"solver": solver_name},
        )
        return _serialize_result(result), {
            "status": status.value,
            "gap": None,
            "iterations": result.solver_iterations,
            "objective_value": result.objective_value,
            "solver": solver_name,
        }


@foundry_method(
    namespace="optimization.stochastic",
    version="1.0.0",
    tags={"optimization", "stochastic-program"},
)
class TwoStageStochasticProgramEstimator:
    runtime_stack: ClassVar[tuple[str, ...]] = ("cvxpy", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="two_stage_stochastic_program",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("objective_vector", SlotType.VECTOR, Unit("objective", "value"), shape=("n_vars",)),
                SlotSpec("technology_matrix", SlotType.MATRIX, Unit("technology", "value"), shape=("n_demands", "n_vars")),
                SlotSpec("scenario_demand_matrix", SlotType.MATRIX, Unit("demand", "value"), shape=("n_scenarios", "n_demands")),
                SlotSpec("scenario_probabilities", SlotType.VECTOR, Unit("probability", "mass"), shape=("n_scenarios",)),
                SlotSpec("recourse_cost_vector", SlotType.VECTOR, Unit("cost", "value"), shape=("n_demands",)),
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
        parameters=(ParameterSpec(name="solver", default="CLARABEL"),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Two-stage stochastic program with shortage recourse under discrete demand scenarios.",
        tags=frozenset({"optimization", "stochastic-program"}),
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
        c = np.asarray(payload["objective_vector"], dtype=float)
        tech = np.asarray(payload["technology_matrix"], dtype=float)
        demand = np.asarray(payload["scenario_demand_matrix"], dtype=float)
        probs = np.asarray(payload["scenario_probabilities"], dtype=float)
        recourse = np.asarray(payload["recourse_cost_vector"], dtype=float)
        bounds = np.asarray(payload["bounds"], dtype=float)
        probs = probs / max(np.sum(probs), 1e-12)

        x = cp.Variable(c.shape[0])
        shortage = cp.Variable((demand.shape[0], demand.shape[1]), nonneg=True)
        lb = bounds[:, 0]
        ub = bounds[:, 1]
        expected_recourse = cp.sum(cp.multiply(probs[:, None], cp.multiply(shortage, recourse[None, :])))
        objective = cp.Maximize(cp.sum(cp.multiply(c, x)) - expected_recourse)
        constraints = [x >= lb]
        finite_ub = np.isfinite(ub)
        if finite_ub.any():
            constraints.append(x[finite_ub] <= ub[finite_ub])
        for scenario_idx in range(demand.shape[0]):
            constraints.append(shortage[scenario_idx] >= demand[scenario_idx] - tech @ x)
        problem = cp.Problem(objective, constraints)

        started = time.perf_counter()
        solver_name = str(params.get("solver", "CLARABEL")).upper()
        solver = _pick_solver(cp, solver_name, "CLARABEL", "SCS", "OSQP")
        problem.solve(solver=solver, verbose=False)
        elapsed = time.perf_counter() - started

        status = _solver_status(problem.status)
        solution = np.zeros(c.shape[0], dtype=float) if x.value is None else np.asarray(x.value, dtype=float)
        expected_cost = 0.0 if shortage.value is None else float(
            np.sum(probs[:, None] * np.asarray(shortage.value, dtype=float) * recourse[None, :])
        )
        result = OptimizationResult(
            status=status,
            objective_value=(None if problem.value is None else float(problem.value)),
            variables={f"x_{idx}": float(solution[idx]) for idx in range(solution.shape[0])},
            constraints_satisfied={"bounds": bool(np.all(solution >= lb - 1e-6))},
            solver_iterations=int(getattr(problem.solver_stats, "num_iters", 0) or 0),
            solver_gap=None,
            solver_time_seconds=float(getattr(problem.solver_stats, "solve_time", elapsed) or elapsed),
            metadata={"solver": solver_name, "expected_recourse_cost": expected_cost},
        )
        return _serialize_result(result), {
            "status": status.value,
            "gap": None,
            "iterations": result.solver_iterations,
            "objective_value": result.objective_value,
            "solver": solver_name,
        }


@foundry_method(
    namespace="optimization.dynamic",
    version="1.0.0",
    tags={"optimization", "dynamic-programming"},
)
class DynamicProgrammingEstimator:
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dynamic_programming",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("reward_tensor", SlotType.TENSOR, Unit("reward", "value"), shape=("n_stages", "n_states", "n_actions")),
                SlotSpec(
                    "transition_tensor",
                    SlotType.TENSOR,
                    Unit("probability", "mass"),
                    shape=("n_stages", "n_states", "n_actions", "n_states"),
                ),
                SlotSpec("initial_state", SlotType.SCALAR, Unit("state", "index")),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("result", "json"),
                    contract_id=OptimizationResult.contract_id,
                )
            }
        ),
        parameters=(ParameterSpec(name="discount_factor", default=1.0),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Finite-horizon dynamic programming over discrete states and actions.",
        tags=frozenset({"optimization", "dynamic-programming"}),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _mapping_payload(state)
        rewards = np.asarray(payload["reward_tensor"], dtype=float)
        transition = np.asarray(payload["transition_tensor"], dtype=float)
        initial_state = int(payload["initial_state"])
        gamma = float(params.get("discount_factor", 1.0))

        n_stages, n_states, n_actions = rewards.shape
        values = np.zeros((n_stages + 1, n_states), dtype=float)
        policy = np.zeros((n_stages, n_states), dtype=int)
        for stage in range(n_stages - 1, -1, -1):
            q_values = rewards[stage] + gamma * np.einsum(
                "san,n->sa",
                transition[stage],
                values[stage + 1],
            )
            policy[stage] = np.argmax(q_values, axis=1)
            values[stage] = np.max(q_values, axis=1)

        current_state = initial_state
        variables: dict[str, float] = {}
        path_reward = 0.0
        for stage in range(n_stages):
            action = int(policy[stage, current_state])
            variables[f"stage_{stage}_action"] = float(action)
            variables[f"stage_{stage}_state"] = float(current_state)
            path_reward += float(rewards[stage, current_state, action]) * (gamma ** stage)
            current_state = int(np.argmax(transition[stage, current_state, action]))

        result = OptimizationResult(
            status=SolverStatus.OPTIMAL,
            objective_value=float(values[0, initial_state]),
            variables=variables,
            constraints_satisfied={"policy_defined": True},
            solver_iterations=int(n_stages * n_states * n_actions),
            solver_gap=0.0,
            solver_time_seconds=0.0,
            metadata={
                "realized_discounted_reward": path_reward,
                "terminal_state": current_state,
                "value_function": values.tolist(),
            },
        )
        return {"result": _serialize_result(result)}


__all__ = [
    "DynamicProgrammingEstimator",
    "SecondOrderConeProgramEstimator",
    "TwoStageStochasticProgramEstimator",
]
