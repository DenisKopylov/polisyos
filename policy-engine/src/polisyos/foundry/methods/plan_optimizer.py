"""
Execution Plan Optimizer for Foundry method chains.

Given a ``CompositionDAG``, produces an ``OptimizedPlan`` that:

1. Partitions nodes into parallel *levels* (Kahn's BFS).
2. Assigns compute backends greedily (JAX where ``supports_jit=True``,
   NumPy otherwise; degrades to NumPy when the JAX circuit breaker is open).
3. Identifies *fusable* consecutive JAX-backend op pairs that share no
   branch point (useful for kernel fusion in future JIT compilation).
4. Estimates wall-clock cost per level using a lightweight ``MethodCostModel``
   that scales by complexity class and input-shape sizes.

Design Principles
-----------------
- **No side effects**: the optimizer reads DAG metadata and returns a
  data-only ``OptimizedPlan`` — it never mutates the DAG or registry.
- **Reuses existing abstractions**: ``CompositionDAG.compute_parallel_levels()``
  for level extraction; ``ComputeBackend`` enum for backend naming.
- **Graceful degradation**: if the JAX circuit breaker is open, affected
  nodes are automatically downgraded to NumPy in the plan.

Usage
-----
::

    from polisyos.foundry.methods.plan_optimizer import ExecutionPlanOptimizer

    optimizer = ExecutionPlanOptimizer()
    plan = optimizer.optimize(
        dag=compiled_chain.dag,
        registry=reg,
        input_shapes={"outcome": (1000,), "covariates": (1000, 5)},
    )
    print(plan.estimated_cost_ms, plan.gpu_scheduled)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from polisyos.foundry.methods.base import ComputeBackend, MethodSignature

__all__ = [
    "OptimizedPlan",
    "NodeSchedule",
    "MethodCostModel",
    "ExecutionPlanOptimizer",
    "ComplexityClass",
]

# ---------------------------------------------------------------------------
# Complexity Classes
# ---------------------------------------------------------------------------

_COMPLEXITY_CLASS_MULTIPLIERS: dict[str, float] = {
    # O(n) or cheaper — lightweight transforms, aggregations
    "O_n": 1.0,
    # O(n log n) — sorts, spectral methods
    "O_nlogn": 2.5,
    # O(n²) — covariance estimation, distance matrices, OLS
    "O_n2": 10.0,
    # O(n³) — matrix inversion, Cholesky, exact GPs
    "O_n3": 100.0,
    # Iterative / solver — LP, MILP, Bayesian MCMC (treated as O_n2 * iter)
    "iterative": 20.0,
    # Structural / graph-based discovery — DAGMA, PC, PCMCI
    "graph": 50.0,
}

# FQN-prefix → complexity class heuristic
_FQN_PREFIX_COMPLEXITY: list[tuple[str, str]] = [
    ("bayesian.mcmc", "iterative"),
    ("bayesian.variational", "iterative"),
    ("bayesian.gp", "O_n3"),
    ("causal.discovery", "graph"),
    ("causal.dagma", "graph"),
    ("causal.pcmci", "graph"),
    ("causal.constraint", "graph"),
    ("causal.gcm", "O_n2"),
    ("causal.dml", "O_n2"),
    ("causal.cate", "O_n2"),
    ("causal.meta", "O_n2"),
    ("causal.policy_learning", "O_n2"),
    ("causal.rdd", "O_n2"),
    ("causal.synthetic_control", "O_n3"),
    ("econometrics.iv", "O_n2"),
    ("econometrics.panel", "O_n2"),
    ("econometrics.timeseries", "O_nlogn"),
    ("econometrics.quantile", "iterative"),
    ("econometrics.factor", "O_n3"),
    ("optimization.lp", "iterative"),
    ("optimization.milp", "iterative"),
    ("optimization.stochastic", "iterative"),
    ("optimization.sequential", "iterative"),
    ("spatial.", "O_n2"),
    ("bayesian.", "O_n2"),
    ("causal.", "O_n2"),
    ("econometrics.", "O_n2"),
    ("optimization.", "iterative"),
]

# Base wall-clock time in ms for a unit-size workload
_BASE_MS_PER_CLASS: dict[str, float] = {
    "O_n": 0.5,
    "O_nlogn": 1.0,
    "O_n2": 5.0,
    "O_n3": 50.0,
    "iterative": 30.0,
    "graph": 200.0,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class ComplexityClass(str):
    """Complexity class string with __repr__ for debug output."""

    def __repr__(self) -> str:
        return f"ComplexityClass({str(self)!r})"


@dataclass(frozen=True)
class NodeSchedule:
    """
    Scheduling decision for a single node in the optimised plan.

    Attributes
    ----------
    node_id:
        UUID of the ``MethodNode``.
    method_fqn:
        Fully-qualified method name.
    assigned_backend:
        Compute backend chosen for this node.
    original_backend:
        Backend declared in ``MethodSignature``.
    degraded:
        ``True`` if the backend was downgraded from the declared one
        (e.g. JAX → NumPy due to an open circuit breaker).
    estimated_ms:
        Estimated wall-clock time for this node alone.
    complexity_class:
        Complexity class string used for the estimate.
    level:
        Parallel-execution level (0-based; same level = concurrent).
    """

    node_id: UUID
    method_fqn: str
    assigned_backend: ComputeBackend
    original_backend: ComputeBackend
    estimated_ms: float
    complexity_class: str
    level: int
    degraded: bool = False


@dataclass
class OptimizedPlan:
    """
    Result of ``ExecutionPlanOptimizer.optimize()``.

    Attributes
    ----------
    levels:
        Node IDs partitioned into parallel levels.  Nodes within the same
        level can execute concurrently; levels must run sequentially.
    schedules:
        Per-node scheduling decisions (``NodeSchedule``).
    estimated_cost_ms:
        Total estimated wall-clock time, accounting for level-wise parallelism
        (cost of a level = max cost among its nodes).
    fusable_pairs:
        List of ``(fqn_a, fqn_b)`` consecutive JAX-backend pairs that share
        no branch point and are candidates for JIT kernel fusion.
    gpu_scheduled:
        FQNs assigned to JAX (GPU-capable) backend.
    cpu_scheduled:
        FQNs assigned to NumPy / non-JAX backend.
    degraded_nodes:
        FQNs where the backend was downgraded from the declared value.
    """

    levels: list[list[UUID]]
    schedules: dict[UUID, NodeSchedule]
    estimated_cost_ms: float
    fusable_pairs: list[tuple[str, str]] = field(default_factory=list)
    gpu_scheduled: list[str] = field(default_factory=list)
    cpu_scheduled: list[str] = field(default_factory=list)
    degraded_nodes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"OptimizedPlan: {len(self.schedules)} nodes, "
            f"{len(self.levels)} levels, "
            f"~{self.estimated_cost_ms:.1f} ms",
            f"  JAX: {len(self.gpu_scheduled)} nodes",
            f"  CPU: {len(self.cpu_scheduled)} nodes",
            f"  Degraded: {len(self.degraded_nodes)} nodes",
            f"  Fusable pairs: {len(self.fusable_pairs)}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# MethodCostModel
# ---------------------------------------------------------------------------


class MethodCostModel:
    """
    Lightweight heuristic cost estimator for individual Foundry methods.

    Estimates are based on:
    - Complexity class derived from the method FQN prefix.
    - Total size of *input* shapes (product of all dimensions).
    - A configurable base-ms per complexity class.

    Parameters
    ----------
    base_ms_overrides:
        Override ``_BASE_MS_PER_CLASS`` entries for tuning.
    calibration:
        ``{fqn: actual_ms}`` from prior runs for exponential smoothing.
    alpha:
        EMA weight for calibration updates (default 0.3).
    """

    def __init__(
        self,
        base_ms_overrides: dict[str, float] | None = None,
        calibration: dict[str, float] | None = None,
        alpha: float = 0.3,
    ) -> None:
        self._base_ms = {**_BASE_MS_PER_CLASS, **(base_ms_overrides or {})}
        self._calibration: dict[str, float] = dict(calibration or {})
        self._alpha = alpha

    def estimate(
        self,
        method_fqn: str,
        input_shapes: dict[str, tuple[int, ...]],
    ) -> tuple[float, str]:
        """
        Estimate execution time for one method invocation.

        Returns
        -------
        (estimated_ms, complexity_class)
        """
        if method_fqn in self._calibration:
            return self._calibration[method_fqn], self._get_complexity_class(method_fqn)

        cls = self._get_complexity_class(method_fqn)
        base = self._base_ms.get(cls, 5.0)
        n = self._total_elements(input_shapes)
        scaled = self._scale(cls, base, n)
        return scaled, cls

    def update(self, fqn: str, actual_ms: float) -> None:
        """Update calibration with an observed execution time."""
        if fqn in self._calibration:
            self._calibration[fqn] = (
                self._alpha * actual_ms + (1 - self._alpha) * self._calibration[fqn]
            )
        else:
            self._calibration[fqn] = actual_ms

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_complexity_class(self, fqn: str) -> str:
        fqn_lower = fqn.lower()
        for prefix, cls in _FQN_PREFIX_COMPLEXITY:
            if fqn_lower.startswith(prefix):
                return cls
        return "O_n2"  # default

    @staticmethod
    def _total_elements(input_shapes: dict[str, tuple[int, ...]]) -> int:
        """Total number of elements across all input arrays."""
        total = 0
        for shape in input_shapes.values():
            if shape:
                from math import prod
                total += prod(shape)
        return max(total, 1)

    def _scale(self, cls: str, base_ms: float, n: int) -> float:
        """Scale base cost by input size for the given complexity class."""
        n_k = n / 1000.0  # normalise to thousands
        if cls == "O_n":
            return base_ms * n_k
        if cls == "O_nlogn":
            return base_ms * n_k * math.log2(max(n_k, 2))
        if cls == "O_n2":
            return base_ms * (n_k ** 2)
        if cls == "O_n3":
            return base_ms * (n_k ** 3)
        # iterative / graph — treat as O_n² with a larger constant
        multiplier = _COMPLEXITY_CLASS_MULTIPLIERS.get(cls, 10.0)
        return base_ms * multiplier * n_k


# ---------------------------------------------------------------------------
# ExecutionPlanOptimizer
# ---------------------------------------------------------------------------


class ExecutionPlanOptimizer:
    """
    Optimises the execution schedule for a ``CompositionDAG``.

    Parameters
    ----------
    cost_model:
        Optional custom ``MethodCostModel``.  Defaults to a fresh instance
        with heuristic baselines.
    check_circuit_breakers:
        If ``True`` (default), nodes whose declared backend has an open
        circuit breaker are downgraded to NumPy in the plan.
    """

    def __init__(
        self,
        cost_model: MethodCostModel | None = None,
        check_circuit_breakers: bool = True,
    ) -> None:
        self._cost_model = cost_model or MethodCostModel()
        self._check_cb = check_circuit_breakers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(
        self,
        dag: Any,  # CompositionDAG — avoid circular import
        registry: Any,  # MethodRegistry
        input_shapes: dict[str, tuple[int, ...]] | None = None,
    ) -> OptimizedPlan:
        """
        Produce an ``OptimizedPlan`` for *dag*.

        Parameters
        ----------
        dag:
            A ``CompositionDAG`` from ``MethodComposer``.
        registry:
            A ``MethodRegistry`` used to look up ``MethodSignature`` objects.
        input_shapes:
            Expected shapes of the initial state keys (used for cost
            estimation).  Unknown shapes default to ``(1000,)``.

        Returns
        -------
        OptimizedPlan
        """
        input_shapes = input_shapes or {}
        open_backends = self._open_circuit_backends() if self._check_cb else set()

        levels: list[list[UUID]] = dag.compute_parallel_levels()

        schedules: dict[UUID, NodeSchedule] = {}
        for level_idx, level in enumerate(levels):
            for node_id in level:
                node = dag.nodes[node_id]
                sig = self._get_signature(node.method_fqn, registry)
                sched = self._schedule_node(
                    node_id=node_id,
                    method_fqn=node.method_fqn,
                    signature=sig,
                    level=level_idx,
                    open_backends=open_backends,
                    input_shapes=input_shapes,
                )
                schedules[node_id] = sched

        estimated_cost_ms = self._estimate_total_cost(levels, schedules)
        fusable_pairs = self._find_fusable_pairs(levels, schedules, dag)
        gpu_scheduled = [s.method_fqn for s in schedules.values()
                         if s.assigned_backend == ComputeBackend.JAX]
        cpu_scheduled = [s.method_fqn for s in schedules.values()
                         if s.assigned_backend != ComputeBackend.JAX]
        degraded = [s.method_fqn for s in schedules.values() if s.degraded]

        return OptimizedPlan(
            levels=levels,
            schedules=schedules,
            estimated_cost_ms=estimated_cost_ms,
            fusable_pairs=fusable_pairs,
            gpu_scheduled=gpu_scheduled,
            cpu_scheduled=cpu_scheduled,
            degraded_nodes=degraded,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _schedule_node(
        self,
        node_id: UUID,
        method_fqn: str,
        signature: MethodSignature | None,
        level: int,
        open_backends: set[str],
        input_shapes: dict[str, tuple[int, ...]],
    ) -> NodeSchedule:
        if signature is not None:
            declared_backend = signature.backend
            supports_jit = signature.supports_jit
        else:
            # Fallback when method not yet in registry
            declared_backend = ComputeBackend.NUMPY
            supports_jit = False

        # Backend assignment: prefer JAX when supports_jit and not open
        if declared_backend == ComputeBackend.JAX and supports_jit:
            if declared_backend.value in open_backends:
                assigned = ComputeBackend.NUMPY
                degraded = True
            else:
                assigned = ComputeBackend.JAX
                degraded = False
        elif declared_backend.value in open_backends:
            assigned = ComputeBackend.NUMPY
            degraded = True
        else:
            assigned = declared_backend
            degraded = False

        estimated_ms, cls = self._cost_model.estimate(method_fqn, input_shapes)

        return NodeSchedule(
            node_id=node_id,
            method_fqn=method_fqn,
            assigned_backend=assigned,
            original_backend=declared_backend,
            estimated_ms=estimated_ms,
            complexity_class=cls,
            level=level,
            degraded=degraded,
        )

    @staticmethod
    def _estimate_total_cost(
        levels: list[list[UUID]],
        schedules: dict[UUID, NodeSchedule],
    ) -> float:
        """
        Total cost = sum of per-level max-cost (parallel execution model).
        """
        total = 0.0
        for level in levels:
            if not level:
                continue
            level_max = max(schedules[nid].estimated_ms for nid in level)
            total += level_max
        return total

    @staticmethod
    def _find_fusable_pairs(
        levels: list[list[UUID]],
        schedules: dict[UUID, NodeSchedule],
        dag: Any,
    ) -> list[tuple[str, str]]:
        """
        Identify consecutive JAX-backend (node_a → node_b) pairs where:
        - node_a is in level k and node_b in level k+1
        - node_b has exactly one predecessor (node_a)
        - both are assigned to JAX

        These are candidates for JIT fusion.
        """
        fusable: list[tuple[str, str]] = []
        for k in range(len(levels) - 1):
            for a_id in levels[k]:
                sched_a = schedules[a_id]
                if sched_a.assigned_backend != ComputeBackend.JAX:
                    continue
                successors = dag.successors.get(a_id, set())
                for b_id in successors:
                    if b_id not in schedules:
                        continue
                    sched_b = schedules[b_id]
                    if sched_b.assigned_backend != ComputeBackend.JAX:
                        continue
                    # Only fuse if b has exactly one predecessor
                    if len(dag.predecessors.get(b_id, set())) == 1:
                        fusable.append((sched_a.method_fqn, sched_b.method_fqn))
        return fusable

    @staticmethod
    def _get_signature(fqn: str, registry: Any) -> MethodSignature | None:
        """Safely retrieve MethodSignature from registry."""
        try:
            method_class = registry.get(fqn)
            return method_class.signature
        except Exception:
            return None

    def _open_circuit_backends(self) -> set[str]:
        """Return backend names with open circuit breakers."""
        try:
            from polisyos.foundry.methods.backends.circuit_breaker import (
                CircuitState,
                get_circuit_breaker_registry,
            )
            reg = get_circuit_breaker_registry()
            return {
                name
                for name, info in reg.health().items()
                if info["state"] == CircuitState.OPEN.value
            }
        except Exception:
            return set()
