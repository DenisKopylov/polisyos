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

    from polisyos.foundry.methods.compiler.plan_optimizer import ExecutionPlanOptimizer

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
from polisyos.foundry.methods.exceptions import FoundryMethodError

__all__ = [
    "ComplexityClass",
    "ExecutionKernel",
    "ExecutionPlanOptimizer",
    "MethodCostModel",
    "NodeSchedule",
    "OptimizedPlan",
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


@dataclass(frozen=True)
class ExecutionKernel:
    """
    Executable optimizer kernel derived from one or more scheduled DAG nodes.

    ``kind='fused_chain'`` represents a linear JAX chain collapsed into one
    kernel boundary. ``kind='batched_level'`` represents multiple peer nodes
    with identical JAX/static shape posture executed as one batched launch.
    ``kind='single'`` is the fallback one-node kernel.
    """

    kind: str
    backend: ComputeBackend
    node_ids: tuple[UUID, ...]
    method_fqns: tuple[str, ...]
    start_level: int
    end_level: int
    estimated_ms: float
    estimated_savings_ms: float
    reason: str


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
    fusion_groups:
        Maximal linear JAX chains that can be executed as one fused kernel.
    batch_groups:
        Same-level JAX nodes that can be auto-batched into one launch.
    execution_kernels:
        Concrete kernel schedule emitted by the optimizer. Covers every node
        exactly once and is consumable by downstream executors.
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
    estimated_optimized_cost_ms: float | None = None
    fusable_pairs: list[tuple[str, str]] = field(default_factory=list)
    fusion_groups: list[tuple[UUID, ...]] = field(default_factory=list)
    batch_groups: list[tuple[UUID, ...]] = field(default_factory=list)
    execution_kernels: list[ExecutionKernel] = field(default_factory=list)
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
            f"  Fusion groups: {len(self.fusion_groups)}",
            f"  Batch groups: {len(self.batch_groups)}",
            f"  Kernel plan: {len(self.execution_kernels)} kernels",
        ]
        if self.estimated_optimized_cost_ms is not None:
            lines.append(f"  Optimized estimate: ~{self.estimated_optimized_cost_ms:.1f} ms")
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
            return base_ms * (n_k**2)
        if cls == "O_n3":
            return base_ms * (n_k**3)
        # Iterative / graph workloads fall back to a linear size term when
        # topology-specific metadata is unavailable; complexity pressure is
        # expressed through the class multiplier instead of a fabricated n² term.
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
        fusion_groups = self._find_fusion_groups(levels, schedules, dag)
        batch_groups = self._find_batch_groups(levels, schedules, dag)
        execution_kernels = self._build_execution_kernels(
            dag=dag,
            schedules=schedules,
            fusion_groups=fusion_groups,
            batch_groups=batch_groups,
        )
        fusable_pairs = [
            (schedules[group[idx]].method_fqn, schedules[group[idx + 1]].method_fqn)
            for group in fusion_groups
            for idx in range(len(group) - 1)
        ]
        gpu_scheduled = [
            s.method_fqn for s in schedules.values() if s.assigned_backend == ComputeBackend.JAX
        ]
        cpu_scheduled = [
            s.method_fqn for s in schedules.values() if s.assigned_backend != ComputeBackend.JAX
        ]
        degraded = [s.method_fqn for s in schedules.values() if s.degraded]

        return OptimizedPlan(
            levels=levels,
            schedules=schedules,
            estimated_cost_ms=estimated_cost_ms,
            estimated_optimized_cost_ms=self._estimate_kernel_cost(execution_kernels),
            fusable_pairs=fusable_pairs,
            fusion_groups=fusion_groups,
            batch_groups=batch_groups,
            execution_kernels=execution_kernels,
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
    def _find_fusion_groups(
        levels: list[list[UUID]],
        schedules: dict[UUID, NodeSchedule],
        dag: Any,
    ) -> list[tuple[UUID, ...]]:
        """Identify maximal linear JAX chains that can be published as one fused kernel."""
        if not schedules:
            return []

        level_by_node = {node_id: sched.level for node_id, sched in schedules.items()}
        visited: set[UUID] = set()
        groups: list[tuple[UUID, ...]] = []

        for level in levels:
            for start_id in level:
                if start_id in visited:
                    continue
                start_sched = schedules[start_id]
                if start_sched.assigned_backend != ComputeBackend.JAX:
                    continue
                preds = dag.predecessors.get(start_id, set())
                if len(preds) == 1:
                    parent_id = next(iter(preds))
                    parent_sched = schedules.get(parent_id)
                    if (
                        parent_sched is not None
                        and parent_sched.assigned_backend == ComputeBackend.JAX
                        and len(dag.successors.get(parent_id, set())) == 1
                    ):
                        continue

                chain = [start_id]
                current_id = start_id
                while True:
                    successors = tuple(sorted(dag.successors.get(current_id, set())))
                    if len(successors) != 1:
                        break
                    next_id = successors[0]
                    next_sched = schedules.get(next_id)
                    if next_sched is None or next_sched.assigned_backend != ComputeBackend.JAX:
                        break
                    if len(dag.predecessors.get(next_id, set())) != 1:
                        break
                    if level_by_node[next_id] != level_by_node[current_id] + 1:
                        break
                    chain.append(next_id)
                    current_id = next_id

                if len(chain) > 1:
                    chain_tuple = tuple(chain)
                    visited.update(chain_tuple)
                    groups.append(chain_tuple)
        return groups

    @staticmethod
    def _find_batch_groups(
        levels: list[list[UUID]],
        schedules: dict[UUID, NodeSchedule],
        dag: Any,
    ) -> list[tuple[UUID, ...]]:
        """Group same-level JAX nodes with the same method/static posture for batched launch."""
        groups: list[tuple[UUID, ...]] = []
        for level in levels:
            buckets: dict[tuple[str, str], list[UUID]] = {}
            for node_id in level:
                sched = schedules[node_id]
                if sched.assigned_backend != ComputeBackend.JAX:
                    continue
                node = dag.nodes[node_id]
                static_digest = (
                    node.node_key.static_params_digest if node.node_key is not None else ""
                )
                key = (sched.method_fqn, static_digest)
                buckets.setdefault(key, []).append(node_id)
            for node_ids in buckets.values():
                if len(node_ids) > 1:
                    groups.append(tuple(node_ids))
        return groups

    @staticmethod
    def _build_execution_kernels(
        *,
        dag: Any,
        schedules: dict[UUID, NodeSchedule],
        fusion_groups: list[tuple[UUID, ...]],
        batch_groups: list[tuple[UUID, ...]],
    ) -> list[ExecutionKernel]:
        """Emit a concrete kernel plan covering every node exactly once."""
        kernels: list[ExecutionKernel] = []
        consumed: set[UUID] = set()

        for group in fusion_groups:
            estimated_ms = ExecutionPlanOptimizer._estimate_fused_kernel_ms(group, schedules)
            base_ms = sum(schedules[node_id].estimated_ms for node_id in group)
            kernels.append(
                ExecutionKernel(
                    kind="fused_chain",
                    backend=ComputeBackend.JAX,
                    node_ids=group,
                    method_fqns=tuple(schedules[node_id].method_fqn for node_id in group),
                    start_level=min(schedules[node_id].level for node_id in group),
                    end_level=max(schedules[node_id].level for node_id in group),
                    estimated_ms=estimated_ms,
                    estimated_savings_ms=max(base_ms - estimated_ms, 0.0),
                    reason="linear_jax_chain",
                )
            )
            consumed.update(group)

        for group in batch_groups:
            if any(node_id in consumed for node_id in group):
                continue
            estimated_ms = ExecutionPlanOptimizer._estimate_batched_kernel_ms(group, schedules)
            base_ms = sum(schedules[node_id].estimated_ms for node_id in group)
            level = schedules[group[0]].level
            kernels.append(
                ExecutionKernel(
                    kind="batched_level",
                    backend=ComputeBackend.JAX,
                    node_ids=group,
                    method_fqns=tuple(schedules[node_id].method_fqn for node_id in group),
                    start_level=level,
                    end_level=level,
                    estimated_ms=estimated_ms,
                    estimated_savings_ms=max(base_ms - estimated_ms, 0.0),
                    reason="same_level_static_batch",
                )
            )
            consumed.update(group)

        for node_id, sched in sorted(
            schedules.items(),
            key=lambda item: (item[1].level, item[1].method_fqn, str(item[0])),
        ):
            if node_id in consumed:
                continue
            kernels.append(
                ExecutionKernel(
                    kind="single",
                    backend=sched.assigned_backend,
                    node_ids=(node_id,),
                    method_fqns=(sched.method_fqn,),
                    start_level=sched.level,
                    end_level=sched.level,
                    estimated_ms=sched.estimated_ms,
                    estimated_savings_ms=0.0,
                    reason="standalone",
                )
            )

        kernels.sort(key=lambda kernel: (kernel.start_level, kernel.kind, kernel.method_fqns))
        return kernels

    @staticmethod
    def _estimate_fused_kernel_ms(
        group: tuple[UUID, ...],
        schedules: dict[UUID, NodeSchedule],
    ) -> float:
        base_ms = sum(schedules[node_id].estimated_ms for node_id in group)
        savings_factor = max(0.70, 0.85 - 0.05 * max(len(group) - 2, 0))
        return base_ms * savings_factor

    @staticmethod
    def _estimate_batched_kernel_ms(
        group: tuple[UUID, ...],
        schedules: dict[UUID, NodeSchedule],
    ) -> float:
        member_costs = [schedules[node_id].estimated_ms for node_id in group]
        max_ms = max(member_costs)
        amortized_launch = 1.0 + 0.15 * max(len(group) - 1, 0)
        return max_ms * amortized_launch

    @staticmethod
    def _estimate_kernel_cost(kernels: list[ExecutionKernel]) -> float:
        """Approximate optimized plan cost by grouping kernels by their start level."""
        by_level: dict[int, list[float]] = {}
        for kernel in kernels:
            by_level.setdefault(kernel.start_level, []).append(kernel.estimated_ms)
        return sum(max(values) for _, values in sorted(by_level.items()))

    @staticmethod
    def _get_signature(fqn: str, registry: Any) -> MethodSignature | None:
        """Safely retrieve MethodSignature from registry."""
        try:
            method_class = registry.get(fqn)
            return method_class.signature
        except (AttributeError, TypeError, ValueError, KeyError, FoundryMethodError):
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
        except (ImportError, AttributeError, KeyError, TypeError, ValueError):
            return set()
