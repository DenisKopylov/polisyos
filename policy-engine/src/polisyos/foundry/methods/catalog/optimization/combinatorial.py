"""Public optimization combinatorial module API."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
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


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


@foundry_method(
    namespace="optimization.combinatorial",
    version="1.0.0",
    tags={"optimization", "combinatorial", "knapsack"},
)
class KnapsackEstimator:
    """Solve knapsack-style resource allocation problems under budget constraints."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="knapsack",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("values", SlotType.VECTOR, Unit("value", "currency"), shape=("n_items",)),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "unit"), shape=("n_items",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="capacity", default=100.0, bounds=(0.0, 1e9)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="0-1 Knapsack via dynamic programming for budget-constrained policy selection.",
        tags=frozenset({"optimization", "combinatorial", "knapsack", "dynamic-programming"}),
        equations={"knapsack": "max sum(v_i*x_i) s.t. sum(w_i*x_i) <= C, x_i in {0,1}"},
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy",),
        when_to_use="Binary project/intervention selection under a budget; portfolio selection with indivisible items",
        citations=(
            "Nemhauser, G. & Wolsey, L. (1988). Integer and Combinatorial Optimization. Wiley.",
        ),
        when_not_to_use="Items are continuously divisible; multiple resource constraints require MILP",
        output_interpretation="Selected item indices + total value and weight. Greedy fallback used for very large capacity instances.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        values = np.asarray(state["values"], dtype=float)
        weights = np.asarray(state["weights"], dtype=float)
        capacity = float(params.get("capacity", 100.0))
        n = len(values)

        # Scale to integer weights for DP (precision 0.01)
        scale = 100.0
        int_weights = np.round(weights * scale).astype(int)
        int_cap = int(round(capacity * scale))

        # DP with memory-efficient approach for large capacities
        if int_cap > 1_000_000:
            # Greedy fractional relaxation for large instances
            ratios = values / np.maximum(weights, 1e-12)
            order = np.argsort(-ratios)
            selected = []
            remaining = capacity
            total_value = 0.0
            for i in order:
                if weights[i] <= remaining:
                    selected.append(int(i))
                    remaining -= weights[i]
                    total_value += values[i]
            return {
                "result": {
                    "selected_items": sorted(selected),
                    "total_value": total_value,
                    "total_weight": capacity - remaining,
                    "capacity": capacity,
                    "n_items": n,
                    "method": "greedy",
                }
            }

        # Standard DP
        dp = np.zeros(int_cap + 1)
        keep = np.zeros((n, int_cap + 1), dtype=bool)

        for i in range(n):
            for c in range(int_cap, int_weights[i] - 1, -1):
                if dp[c - int_weights[i]] + values[i] > dp[c]:
                    dp[c] = dp[c - int_weights[i]] + values[i]
                    keep[i, c] = True

        # Backtrack
        selected = []
        c = int_cap
        for i in range(n - 1, -1, -1):
            if keep[i, c]:
                selected.append(i)
                c -= int_weights[i]

        selected = sorted(selected)
        total_val = float(np.sum(values[selected])) if selected else 0.0
        total_wt = float(np.sum(weights[selected])) if selected else 0.0

        return {
            "result": {
                "selected_items": selected,
                "total_value": total_val,
                "total_weight": total_wt,
                "capacity": capacity,
                "n_items": n,
                "method": "dynamic_programming",
            }
        }


@foundry_method(
    namespace="optimization.combinatorial",
    version="1.0.0",
    tags={"optimization", "combinatorial", "vehicle-routing"},
)
class VehicleRoutingEstimator:
    """Solve vehicle-routing style service-allocation problems over networked demand."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="vehicle_routing",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("distance_matrix", SlotType.MATRIX, Unit("distance", "km"), shape=("n_nodes", "n_nodes")),
                SlotSpec("demands", SlotType.VECTOR, Unit("demand", "unit"), shape=("n_nodes",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="vehicle_capacity", default=100.0, bounds=(1.0, 1e6)),
            ParameterSpec(name="n_vehicles", default=3),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Capacitated Vehicle Routing Problem via nearest-neighbor heuristic.",
        tags=frozenset({"optimization", "combinatorial", "vehicle-routing", "cvrp", "heuristic"}),
        equations={"cvrp": "min total distance s.t. capacity constraints per vehicle"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Service delivery route optimization; facility-to-client assignment with capacity limits; logistics policy design",
        when_not_to_use="Exact optimal route required (use MILP/branch-and-bound); problem has time-window constraints",
        output_interpretation="Routes per vehicle + total distance. Unserved nodes listed if vehicle count is insufficient. Heuristic — solution is near-optimal, not guaranteed optimal.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        D = np.asarray(state["distance_matrix"], dtype=float)
        demands = np.asarray(state["demands"], dtype=float)
        cap = float(params.get("vehicle_capacity", 100.0))
        n_vehicles = int(params.get("n_vehicles", 3))
        n = len(demands)

        # Node 0 is depot
        unvisited = set(range(1, n))
        routes = []
        total_distance = 0.0

        for _ in range(n_vehicles):
            if not unvisited:
                break
            route = [0]
            load = 0.0
            current = 0

            while unvisited:
                # Find nearest feasible
                best_next = None
                best_dist = float("inf")
                for j in unvisited:
                    if load + demands[j] <= cap and D[current, j] < best_dist:
                        best_dist = D[current, j]
                        best_next = j

                if best_next is None:
                    break

                route.append(best_next)
                load += demands[best_next]
                total_distance += best_dist
                current = best_next
                unvisited.remove(best_next)

            # Return to depot
            total_distance += float(D[current, 0])
            route.append(0)
            routes.append(route)

        return {
            "result": {
                "routes": routes,
                "total_distance": total_distance,
                "n_routes_used": len(routes),
                "unserved_nodes": sorted(unvisited),
                "n_nodes": n,
            }
        }


__all__ = [
    "KnapsackEstimator",
    "VehicleRoutingEstimator",
]
