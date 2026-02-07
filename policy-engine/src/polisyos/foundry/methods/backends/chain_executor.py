from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID

from polisyos.foundry.methods.backends.adapters import adapt_state
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import MethodResult
from polisyos.foundry.methods.registry import MethodRegistry


@dataclass(frozen=True, slots=True)
class ChainExecutionResult:
    final_state: Any
    node_results: tuple[tuple[UUID, MethodResult], ...]

    @property
    def total_wall_time_ms(self) -> float:
        return sum(result.timing.wall_time_ms for _, result in self.node_results)


def execute_heterogeneous_chain(
    chain: Any,
    *,
    state: Any,
    params_per_node: Mapping[UUID, Mapping[str, Any]] | None = None,
    seed: int = 0,
    registry: MethodRegistry | None = None,
    dispatcher: MethodDispatcher | None = None,
) -> ChainExecutionResult:
    reg = registry or MethodRegistry.get_instance()
    disp = dispatcher or MethodDispatcher.get_instance()

    current_state = state
    prev_backend = None
    node_results: list[tuple[UUID, MethodResult]] = []

    for node_id in chain.execution_order:
        node = chain.get_node(node_id)
        signature = chain.get_signature(node_id)
        method_class = reg.get(signature.fqn)

        combined_params = dict(node.static_params)
        combined_params.update(node.params)
        if params_per_node and node_id in params_per_node:
            combined_params.update(params_per_node[node_id])

        if prev_backend is not None and prev_backend is not signature.backend:
            current_state = adapt_state(
                current_state,
                source_backend=prev_backend,
                target_backend=signature.backend,
            )

        result = disp.dispatch(
            method_class=method_class,
            signature=signature,
            state=current_state,
            params=combined_params,
            seed=seed,
        )
        current_state = result.output
        prev_backend = signature.backend
        node_results.append((node_id, result))

    return ChainExecutionResult(
        final_state=current_state,
        node_results=tuple(node_results),
    )

