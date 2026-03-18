"""
Ray-distributed chain executor for Foundry method chains.

``RayChainExecutor`` extends the async chain executor's level-by-level
parallelism to a Ray cluster.  All nodes within the same topological
*level* are submitted to Ray simultaneously; the executor waits for all
tasks in a level to complete before starting the next level.

Architecture
------------
- Each node becomes a Ray remote task via ``RayMethodRunner.run()``.
- State is shallow-merged level-by-level (same semantics as
  ``AsyncChainExecutor``).
- The executor is **stateless** — it can be reused across calls.

Usage
-----
::

    import ray
    ray.init()

    from polisyos.foundry.methods.backends.ray_chain_executor import RayChainExecutor

    executor = RayChainExecutor(num_cpus_per_node=2)
    result = executor.execute(chain, initial_state=state)
    print(result.total_wall_time_ms)

    ray.shutdown()

Limitations
-----------
- State objects must be Ray-serialisable (picklable).
- JAX arrays on the local device are pickled as NumPy arrays — this is
  correct but may add serialisation overhead for large tensors.
- Bindings between nodes are resolved *locally* by the executor process,
  not inside Ray workers.  This means slot routing is synchronous.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID

from polisyos.foundry.methods._logging import get_foundry_logger
from polisyos.foundry.methods.backends.chain_executor import ChainExecutionResult
from polisyos.foundry.methods.backends.ray_runner import (
    RayMethodRunner,
    RayNotAvailableError,
    RayTaskResult,
)
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.base import ComputeBackend
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.registry import MethodRegistry

_log = get_foundry_logger("foundry.backends.ray_chain")

__all__ = [
    "RayChainExecutor",
    "RayChainExecutionError",
]


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

@dataclass
class RayChainExecutionError(RuntimeError):
    """Raised when one or more nodes fail during Ray chain execution."""

    failures: list[tuple[str, Exception]]  # [(fqn, exc), ...]

    def __str__(self) -> str:
        lines = [f"RayChainExecutionError: {len(self.failures)} node(s) failed:"]
        for fqn, exc in self.failures:
            lines.append(f"  {fqn}: {exc}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# RayChainExecutor
# ---------------------------------------------------------------------------

class RayChainExecutor:
    """
    Executes a compiled method chain distributed across a Ray cluster.

    Nodes at the same topological level run concurrently as Ray tasks.
    Levels are executed sequentially — each level depends on the previous.

    Parameters
    ----------
    num_cpus_per_node:
        CPUs allocated per Ray task.  Default 1.
    memory_per_node:
        Memory (bytes) per Ray task.  Default None.
    timeout_per_node:
        Seconds before a single node times out.  Default None (infinite).
    registry:
        Method registry for resolving FQNs.  Defaults to the global singleton.
    """

    def __init__(
        self,
        *,
        num_cpus_per_node: float = 1.0,
        memory_per_node: int | None = None,
        timeout_per_node: float | None = None,
        registry: MethodRegistry | None = None,
    ) -> None:
        self._runner = RayMethodRunner(
            num_cpus=num_cpus_per_node,
            memory=memory_per_node,
            timeout=timeout_per_node,
        )
        self._registry = registry

    def is_available(self) -> bool:
        """Return True if Ray is installed and initialised."""
        return self._runner.is_available()

    def execute(
        self,
        chain: Any,
        *,
        initial_state: Any,
        params_per_node: Mapping[UUID, Mapping[str, Any]] | None = None,
    ) -> ChainExecutionResult:
        """
        Execute *chain* level-by-level on Ray workers.

        Parameters
        ----------
        chain:
            A ``CompiledMethodChain`` from ``MethodComposer.build()``.
        initial_state:
            Initial state dict passed to the first level's methods.
        params_per_node:
            Per-node parameter overrides keyed by node UUID.

        Returns
        -------
        ChainExecutionResult
            Same structure as the local chain executor result.

        Raises
        ------
        RayNotAvailableError
            If Ray is not installed or not initialised.
        RayChainExecutionError
            If one or more nodes raise during execution.
        """
        if not self.is_available():
            raise RayNotAvailableError(
                "Ray is not available. Install with 'pip install ray[default]' "
                "and call ray.init() before executing."
            )

        reg = self._registry or MethodRegistry.get_instance()

        # Get level partition from the DAG.
        levels = chain.dag.compute_parallel_levels()
        total_nodes = sum(len(lvl) for lvl in levels)

        chain_t0 = time.perf_counter()
        _log.info("chain_start", total_nodes=total_nodes, levels=len(levels))

        current_state: dict[str, Any] = dict(initial_state) if isinstance(initial_state, dict) else {"__state__": initial_state}
        node_results: list[tuple[UUID, MethodResult]] = []
        node_slot_outputs: dict[UUID, dict[str, Any]] = {}

        for level_idx, level_node_ids in enumerate(levels):
            level_t0 = time.perf_counter()
            _log.info("chain_level_start", level=level_idx, nodes=len(level_node_ids))

            # Build per-node inputs from slot bindings.
            node_states: dict[UUID, dict[str, Any]] = {}
            for node_id in level_node_ids:
                node_state = dict(current_state)
                for binding in chain.get_bindings_for_target(node_id):
                    source_id = binding.source_node_id
                    if source_id is not None and source_id in node_slot_outputs:
                        src_output = node_slot_outputs[source_id]
                        if binding.source_slot in src_output:
                            node_state[binding.target_slot] = src_output[binding.source_slot]
                node_states[node_id] = node_state

            # Submit all nodes in this level as Ray tasks concurrently.
            futures: dict[UUID, Any] = {}
            method_classes: dict[UUID, Any] = {}
            failures: list[tuple[str, Exception]] = []

            for node_id in level_node_ids:
                node = chain.get_node(node_id)
                sig = chain.get_signature(node_id)

                combined_params: dict[str, Any] = dict(node.static_params)
                combined_params.update(node.params)
                if params_per_node and node_id in params_per_node:
                    combined_params.update(params_per_node[node_id])

                method_class = reg.get(sig.fqn)
                method_classes[node_id] = method_class

                try:
                    # Submit to Ray (non-blocking — returns immediately)
                    import ray
                    from polisyos.foundry.methods.backends.ray_runner import _remote_pure_step

                    remote_kwargs: dict[str, Any] = {"num_cpus": self._runner._num_cpus}
                    if self._runner._memory is not None:
                        remote_kwargs["memory"] = self._runner._memory

                    remote_fn = ray.remote(**remote_kwargs)(_remote_pure_step)
                    ref = remote_fn.remote(
                        sig.fqn,
                        method_class.pure_step,
                        node_states[node_id],
                        combined_params,
                    )
                    futures[node_id] = ref
                except Exception as exc:
                    failures.append((sig.fqn, exc))

            # Collect results for this level.
            for node_id in level_node_ids:
                if node_id not in futures:
                    continue  # already failed during submission

                sig = chain.get_signature(node_id)
                try:
                    import ray
                    result_tuple = ray.get(
                        futures[node_id], timeout=self._runner._timeout
                    )
                    fqn, output, wall_ms, _pid = result_tuple

                    node_slot_outputs[node_id] = output
                    current_state.update(output)

                    timing = MethodTiming(wall_time_ms=wall_ms)
                    reproducibility = ReproducibilityInfo(
                        backend=ComputeBackend.NUMPY,
                        determinism_tier=DeterminismTier.DETERMINISTIC,
                        note="ray-distributed",
                    )
                    node_results.append((
                        node_id,
                        MethodResult(
                            output=output,
                            timing=timing,
                            reproducibility=reproducibility,
                        ),
                    ))
                except Exception as exc:
                    failures.append((sig.fqn, exc))

            if failures:
                raise RayChainExecutionError(failures=failures)

            level_elapsed = (time.perf_counter() - level_t0) * 1000.0
            _log.info(
                "chain_level_complete",
                level=level_idx,
                elapsed_ms=round(level_elapsed, 2),
            )

        chain_elapsed = (time.perf_counter() - chain_t0) * 1000.0
        _log.info("chain_complete", elapsed_ms=round(chain_elapsed, 2), nodes=total_nodes)

        return ChainExecutionResult(
            final_state=current_state,
            node_results=tuple(node_results),
        )

    def __repr__(self) -> str:
        return (
            f"<RayChainExecutor "
            f"num_cpus_per_node={self._runner._num_cpus} "
            f"available={self.is_available()}>"
        )
