"""
Async Chain Executor — parallel execution of independent DAG levels.

``AsyncChainExecutor`` parallelises method chains by executing all nodes
within the same topological *level* concurrently via ``asyncio.gather``.
Nodes at different levels are still executed sequentially (level k must
complete before level k+1 starts) because nodes in higher levels may
consume outputs produced by nodes in lower levels.

Design
------
- Each node is dispatched in a thread pool via ``asyncio.to_thread`` so
  that CPU-bound ``pure_step`` calls don't block the event loop.
- An optional *per-node timeout* is enforced via ``asyncio.timeout``
  (Python 3.11+).  Set ``timeout_per_node=None`` (default) to disable.
- Errors in individual nodes are collected and re-raised as an
  ``AsyncChainExecutionError`` that aggregates all failures.
- State is merged level-by-level: each node's ``output`` dict is shallow-
  merged into a shared mutable state dict so that subsequent nodes can
  read upstream results.

Usage
-----
::

    import asyncio
    from polisyos.foundry.methods.backends.async_chain_executor import AsyncChainExecutor

    executor = AsyncChainExecutor()
    result = asyncio.run(
        executor.execute(chain, initial_state=state, params_map={})
    )
    print(result.total_wall_time_ms)

Thread safety
-------------
``AsyncChainExecutor`` itself is stateless and can be reused across calls.
The shared *state dict* is only mutated between levels, never within a
level, so no additional locking is needed.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from polisyos.foundry.methods._logging import get_foundry_logger
from polisyos.foundry.methods.backends.adapters import adapt_state
from polisyos.foundry.methods.backends.chain_executor import (
    ChainExecutionResult,
    _build_level_parallel_reproducibility_contract,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import MethodResult
from polisyos.foundry.methods.exceptions import MethodContractError
from polisyos.foundry.methods.io import materialize_method_input, validate_value_for_slot
from polisyos.foundry.methods.registry import MethodRegistry, get_registry

_log = get_foundry_logger("foundry.backends.async_chain")

__all__ = [
    "AsyncChainExecutionError",
    "AsyncChainExecutor",
    "AsyncNodeError",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


@dataclass
class AsyncNodeError:
    """Details of a single node failure during async execution."""

    node_id: UUID
    method_fqn: str
    error: Exception

    def __str__(self) -> str:
        return f"[{self.method_fqn}] {type(self.error).__name__}: {self.error}"


class AsyncChainExecutionError(Exception):
    """
    Raised when one or more nodes in an async chain fail.

    All node errors are collected so that callers can diagnose multiple
    failures in a single run rather than stopping at the first error.
    """

    def __init__(self, node_errors: list[AsyncNodeError]) -> None:
        msgs = "\n  ".join(str(e) for e in node_errors)
        super().__init__(f"{len(node_errors)} node(s) failed:\n  {msgs}")
        self.node_errors = node_errors


# ---------------------------------------------------------------------------
# AsyncChainExecutor
# ---------------------------------------------------------------------------


class AsyncChainExecutor:
    """
    Executes a ``CompiledMethodChain`` with level-wise parallelism.

    Parameters
    ----------
    dispatcher:
        Optional ``MethodDispatcher`` to use.  Defaults to the global singleton.
    registry:
        Optional ``MethodRegistry`` to use.  Defaults to ``get_registry()``.
    """

    def __init__(
        self,
        dispatcher: MethodDispatcher | None = None,
        registry: MethodRegistry | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._registry = registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self,
        chain: Any,  # CompiledMethodChain — avoid circular import
        initial_state: Any,
        params_map: Mapping[UUID, Mapping[str, Any]] | None = None,
        *,
        fx_rate_provider: Any | None = None,
        timeout_per_node: float | None = None,
        seed: int = 0,
    ) -> ChainExecutionResult:
        """
        Execute *chain* with level-wise parallelism.

        Parameters
        ----------
        chain:
            A ``CompiledMethodChain`` produced by ``MethodComposer.build()``.
        initial_state:
            Initial state dict passed to the first level.
        params_map:
            Mapping from node UUID to parameter dict.  Nodes not in the
            map receive an empty parameter dict.
        timeout_per_node:
            Per-node wall-clock timeout in seconds.  ``None`` = no timeout.
        seed:
            Random seed threaded through for reproducibility.

        Returns
        -------
        ChainExecutionResult
            Aggregated results including final state and per-node timing.

        Raises
        ------
        AsyncChainExecutionError
            If any node raises an exception.
        """
        reg = self._registry or get_registry()
        disp = self._dispatcher or MethodDispatcher.get_instance()
        params_map = params_map or {}

        # Get parallel levels from the DAG
        levels: list[list[UUID]] = chain.dag.compute_parallel_levels()
        total_nodes = sum(len(lvl) for lvl in levels)

        _log.info("chain_start", total_levels=len(levels), total_nodes=total_nodes)
        chain_t0 = time.perf_counter()

        state: Any = dict(initial_state) if isinstance(initial_state, dict) else initial_state
        all_node_results: list[tuple[UUID, MethodResult]] = []
        node_slot_outputs: dict[UUID, dict[str, Any]] = {}

        for level_idx, level in enumerate(levels):
            _log.debug("chain_level_start", level_idx=level_idx, level_size=len(level))
            level_t0 = time.perf_counter()

            level_results = await self._execute_level(
                level=level,
                chain=chain,
                state=state,
                params_map=params_map,
                slot_outputs=node_slot_outputs,
                fx_rate_provider=fx_rate_provider,
                timeout_per_node=timeout_per_node,
                registry=reg,
                dispatcher=disp,
                seed=seed,
            )
            # Merge outputs into shared state
            for node_id, result in level_results:
                all_node_results.append((node_id, result))
                node_slot_outputs[node_id] = dict(result.slot_outputs)
                if isinstance(result.output, dict):
                    if isinstance(state, dict):
                        state.update(result.output)
                    else:
                        state = dict(result.output)
                else:
                    state = result.output

            level_elapsed_ms = (time.perf_counter() - level_t0) * 1000
            _log.debug(
                "chain_level_complete",
                level_idx=level_idx,
                level_size=len(level),
                elapsed_ms=round(level_elapsed_ms, 2),
            )

        chain_elapsed_ms = (time.perf_counter() - chain_t0) * 1000
        _log.info(
            "chain_complete",
            total_levels=len(levels),
            total_nodes=len(all_node_results),
            total_wall_time_ms=round(chain_elapsed_ms, 2),
        )

        return ChainExecutionResult(
            final_state=state,
            node_results=tuple(all_node_results),
            reproducibility_contract=_build_level_parallel_reproducibility_contract(
                levels,
                all_node_results,
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _execute_level(
        self,
        level: list[UUID],
        chain: Any,
        state: Any,
        params_map: Mapping[UUID, Mapping[str, Any]],
        slot_outputs: Mapping[UUID, Mapping[str, Any]],
        fx_rate_provider: Any | None,
        timeout_per_node: float | None,
        registry: MethodRegistry,
        dispatcher: MethodDispatcher,
        seed: int,
    ) -> list[tuple[UUID, MethodResult]]:
        """Execute all nodes in *level* concurrently."""
        tasks = [
            self._dispatch_node(
                node_id=node_id,
                chain=chain,
                state=state if not isinstance(state, dict) else dict(state),
                params=dict(params_map.get(node_id, {})),
                slot_outputs=slot_outputs,
                fx_rate_provider=fx_rate_provider,
                timeout=timeout_per_node,
                registry=registry,
                dispatcher=dispatcher,
                seed=seed,
            )
            for node_id in level
        ]

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate successes from failures
        node_errors: list[AsyncNodeError] = []
        level_results: list[tuple[UUID, MethodResult]] = []

        for node_id, raw in zip(level, raw_results, strict=True):
            if isinstance(raw, BaseException):
                node = chain.get_node(node_id)
                node_errors.append(
                    AsyncNodeError(
                        node_id=node_id,
                        method_fqn=node.method_fqn,
                        error=raw,
                    )
                )
            else:
                level_results.append((node_id, raw))

        if node_errors:
            raise AsyncChainExecutionError(node_errors)

        return level_results

    async def _dispatch_node(
        self,
        node_id: UUID,
        chain: Any,
        state: Any,
        params: dict[str, Any],
        slot_outputs: Mapping[UUID, Mapping[str, Any]],
        fx_rate_provider: Any | None,
        timeout: float | None,
        registry: MethodRegistry,
        dispatcher: MethodDispatcher,
        seed: int,
    ) -> MethodResult:
        """Dispatch a single node asynchronously."""
        from polisyos.foundry.methods.backends import chain_executor as chain_exec

        node = chain.get_node(node_id)
        method_class = registry.get(node.method_fqn)
        signature = chain.get_signature(node_id)

        # Merge node-level params with chain-level params
        node_params = dict(node.params)
        node_params.update(params)
        node_params.setdefault("seed", seed)

        bound_inputs: dict[str, Any] = {}
        for binding in chain.get_bindings_for_target(node_id):
            source_node_id = binding.source_node_id
            if source_node_id is None:
                raise MethodContractError(
                    signature.fqn,
                    f"binding for target slot '{binding.target_slot}' is missing source_node_id",
                )
            source_outputs = slot_outputs.get(source_node_id)
            if source_outputs is None:
                raise MethodContractError(
                    signature.fqn,
                    (
                        f"binding source node {source_node_id} for target slot "
                        f"'{binding.target_slot}' has not produced slot outputs"
                    ),
                )
            if binding.source_slot not in source_outputs:
                raise MethodContractError(
                    signature.fqn,
                    (
                        f"source slot '{binding.source_slot}' was not produced by "
                        f"{binding.source_method}"
                    ),
                )

            source_value = source_outputs[binding.source_slot]
            source_backend = chain.get_signature(source_node_id).backend
            if source_backend is not signature.backend:
                source_value = adapt_state(
                    source_value,
                    source_backend=source_backend,
                    target_backend=signature.backend,
                )
            source_value = chain_exec._apply_binding_adapters(
                source_value,
                binding=binding,
                target_backend=signature.backend,
                fx_rate_provider=fx_rate_provider,
                context=state,
            )

            target_slot = signature.get_input_slot(binding.target_slot)
            if target_slot is None:
                raise MethodContractError(
                    signature.fqn,
                    f"target slot '{binding.target_slot}' is not declared by method",
                )
            validate_value_for_slot(
                target_slot,
                source_value,
                method_fqn=signature.fqn,
                label="input",
            )
            bound_inputs[binding.target_slot] = source_value

        materialized_state = materialize_method_input(
            method_class=method_class,
            signature=signature,
            bound_inputs=bound_inputs,
            fallback_state=state,
        )

        async def _run() -> MethodResult:
            return await asyncio.to_thread(
                dispatcher.dispatch,
                method_class=method_class,
                signature=signature,
                state=materialized_state,
                params=node_params,
                seed=seed,
            )

        if timeout is not None:
            async with asyncio.timeout(timeout):
                return await _run()
        return await _run()
