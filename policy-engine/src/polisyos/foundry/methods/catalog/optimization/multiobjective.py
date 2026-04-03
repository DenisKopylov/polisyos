"""Public optimization multiobjective module API."""
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


@foundry_method(
    namespace="optimization.multiobjective",
    version="1.0.0",
    tags={"optimization", "multiobjective", "nsga2"},
)
class MultiObjectiveNSGA2Estimator:
    """Search Pareto-efficient policy designs with NSGA-II when objectives conflict."""
    runtime_stack: ClassVar[tuple[str, ...]] = ("pymoo", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="multiobjective_nsga2",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "objective_matrix",
                    SlotType.MATRIX,
                    Unit("objective", "value"),
                    shape=("n_items", "n_objectives"),
                ),
                SlotSpec("cost_vector", SlotType.VECTOR, Unit("cost", "value"), shape=("n_items",)),
                SlotSpec("budget", SlotType.SCALAR, Unit("budget", "value")),
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
            ParameterSpec(name="n_generations", default=80),
            ParameterSpec(name="pop_size", default=80),
            ParameterSpec(name="selection_threshold", default=0.5),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="NSGA-II search for Pareto-efficient selections under a budget.",
        tags=frozenset({"optimization", "multiobjective", "nsga2"}),
        when_to_use="Multiple conflicting objectives; policy trade-off analysis (equity vs efficiency); Pareto frontier",
        citations=(
            "Deb, K. et al. (2002). A fast and elitist multiobjective genetic algorithm: NSGA-II. IEEE Transactions on Evolutionary Computation, 6(2), 182-197.",
        ),
        when_not_to_use="Single objective problem; objectives can be aggregated with known weights",
        output_interpretation="Pareto-optimal set. Each solution is undominated. Decision-maker selects preferred trade-off point.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> Mapping[str, Any]:
        payload = _mapping_payload(fallback_state) if isinstance(fallback_state, Mapping) else {}
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        from pymoo.algorithms.moo.nsga2 import NSGA2
        from pymoo.core.problem import ElementwiseProblem
        from pymoo.optimize import minimize

        payload = _mapping_payload(state)
        objective_matrix = np.asarray(payload["objective_matrix"], dtype=float)
        cost_vector = np.asarray(payload["cost_vector"], dtype=float)
        budget = float(payload["budget"])
        if objective_matrix.ndim != 2 or cost_vector.ndim != 1:
            raise ValueError("objective_matrix must be 2D and cost_vector must be 1D")
        if objective_matrix.shape[0] != cost_vector.shape[0]:
            raise ValueError("objective_matrix rows must match cost_vector length")

        threshold = float(params.get("selection_threshold", 0.5))

        class _SelectionProblem(ElementwiseProblem):
            def __init__(self) -> None:
                super().__init__(
                    n_var=objective_matrix.shape[0],
                    n_obj=objective_matrix.shape[1],
                    n_ieq_constr=1,
                    xl=0.0,
                    xu=1.0,
                )

            def _evaluate(self, x, out, *args, **kwargs) -> None:
                binary = (np.asarray(x, dtype=float) >= threshold).astype(float)
                out["F"] = -(binary @ objective_matrix)
                out["G"] = [float(binary @ cost_vector - budget)]

        algorithm = NSGA2(
            pop_size=max(20, int(params.get("pop_size", 80))),
        )
        generations = max(10, int(params.get("n_generations", 80)))
        started = time.perf_counter()
        res = minimize(
            _SelectionProblem(),
            algorithm,
            termination=("n_gen", generations),
            seed=int(params.get("__seed__", 0)),
            verbose=False,
        )
        elapsed = time.perf_counter() - started

        if res.X is None or res.F is None:
            result = OptimizationResult(
                status=SolverStatus.INFEASIBLE,
                objective_value=None,
                variables={},
                constraints_satisfied={"budget": False},
                solver_iterations=generations,
                solver_gap=None,
                solver_time_seconds=elapsed,
                metadata={"pareto_front": [], "reason": "no feasible solutions found"},
            )
            solver_info = {
                "status": SolverStatus.INFEASIBLE.value,
                "gap": None,
                "iterations": generations,
                "objective_value": None,
                "solver": "NSGA2",
            }
            return _serialize_result(result), solver_info

        solutions = np.asarray(res.X, dtype=float)
        objectives = -np.asarray(res.F, dtype=float)
        if solutions.ndim == 1:
            solutions = solutions.reshape(1, -1)
            objectives = objectives.reshape(1, -1)
        binary_solutions = (solutions >= threshold).astype(float)
        feasible_mask = np.sum(binary_solutions * cost_vector[None, :], axis=1) <= budget + 1e-6
        feasible_solutions = binary_solutions[feasible_mask]
        feasible_objectives = objectives[feasible_mask]
        if feasible_solutions.shape[0] == 0:
            feasible_solutions = binary_solutions
            feasible_objectives = objectives

        normalized = feasible_objectives / np.maximum(
            np.max(np.abs(feasible_objectives), axis=0, keepdims=True),
            1e-8,
        )
        scores = np.sum(normalized, axis=1)
        best_idx = int(np.argmax(scores))
        selected = feasible_solutions[best_idx]
        selected_objectives = feasible_objectives[best_idx]
        total_cost = float(selected @ cost_vector)
        aggregate_score = float(np.sum(selected_objectives))
        result = OptimizationResult(
            status=SolverStatus.OPTIMAL,
            objective_value=aggregate_score,
            variables={f"x_{idx}": float(selected[idx]) for idx in range(selected.shape[0])},
            constraints_satisfied={"budget": bool(total_cost <= budget + 1e-6)},
            solver_iterations=generations,
            solver_gap=None,
            solver_time_seconds=elapsed,
            metadata={
                "selected_objectives": [float(value) for value in selected_objectives],
                "total_cost": total_cost,
                "pareto_front": feasible_objectives.tolist(),
            },
        )
        solver_info = {
            "status": SolverStatus.OPTIMAL.value,
            "gap": None,
            "iterations": generations,
            "objective_value": aggregate_score,
            "solver": "NSGA2",
        }
        return _serialize_result(result), solver_info


__all__ = ["MultiObjectiveNSGA2Estimator"]
