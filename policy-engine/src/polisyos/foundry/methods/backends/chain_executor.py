from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping
from uuid import UUID

import numpy as np

from polisyos.foundry.methods.backends.adapters import adapt_state
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import MethodResult
from polisyos.foundry.methods.base import ComputeBackend
from polisyos.foundry.methods.exceptions import MethodContractError
from polisyos.foundry.methods.io import materialize_method_input, validate_value_for_slot
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.types.checker import ShapeAdapterKind


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
    current_context = state
    prev_backend = None
    node_results: list[tuple[UUID, MethodResult]] = []
    node_slot_outputs: dict[UUID, dict[str, Any]] = {}

    for node_id in chain.execution_order:
        node = chain.get_node(node_id)
        signature = chain.get_signature(node_id)
        method_class = reg.get(signature.fqn)

        combined_params = dict(node.static_params)
        combined_params.update(node.params)
        if params_per_node and node_id in params_per_node:
            combined_params.update(params_per_node[node_id])

        if prev_backend is not None and prev_backend is not signature.backend:
            current_context = _adapt_execution_context(
                current_context,
                source_backend=prev_backend,
                target_backend=signature.backend,
            )

        bound_inputs: dict[str, Any] = {}
        for binding in chain.get_bindings_for_target(node_id):
            source_node_id = binding.source_node_id
            if source_node_id is None:
                raise MethodContractError(
                    signature.fqn,
                    f"binding for target slot '{binding.target_slot}' is missing source_node_id",
                )
            source_outputs = node_slot_outputs.get(source_node_id)
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
            source_value = _apply_binding_adapters(
                source_value,
                binding=binding,
                target_backend=signature.backend,
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
            fallback_state=current_context,
        )

        result = disp.dispatch(
            method_class=method_class,
            signature=signature,
            state=materialized_state,
            params=combined_params,
            seed=seed,
        )
        current_state = result.output
        current_context = _merge_execution_context(current_context, result.output)
        prev_backend = signature.backend
        node_results.append((node_id, result))
        node_slot_outputs[node_id] = dict(result.slot_outputs)

    return ChainExecutionResult(
        final_state=current_state,
        node_results=tuple(node_results),
    )


def _adapt_execution_context(
    state: Any,
    *,
    source_backend: ComputeBackend,
    target_backend: ComputeBackend,
) -> Any:
    if isinstance(state, Mapping):
        return state
    return adapt_state(
        state,
        source_backend=source_backend,
        target_backend=target_backend,
    )


def _merge_execution_context(previous_state: Any, output: Any) -> Any:
    if not isinstance(output, Mapping):
        return output

    base_context = _state_context_mapping(previous_state)
    merged = dict(base_context or {})
    merged.update(output)
    return merged


def _state_context_mapping(state: Any) -> dict[str, Any] | None:
    if isinstance(state, Mapping):
        return dict(state)

    aliases = _state_aliases(state)
    if aliases:
        return aliases
    return None


def _state_aliases(state: Any) -> dict[str, Any]:
    if state is None:
        return {}

    class_name = type(state).__name__
    if not class_name:
        return {}

    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()
    aliases = {snake: state}

    normalized = snake.replace("__", "_")
    if normalized.endswith("panel_data") or "panel_observational_data" in normalized:
        aliases.setdefault("panel_data", state)
    if normalized.endswith("time_series_data"):
        aliases.setdefault("time_series_data", state)
    if normalized.endswith("tabular_data"):
        aliases.setdefault("tabular_data", state)
    if normalized.endswith("survey_micro_data"):
        aliases.setdefault("survey_micro_data", state)
    if normalized.endswith("prediction_result"):
        aliases.setdefault("prediction_result", state)
    if normalized.endswith("graph_causal_data"):
        aliases.setdefault("graph_causal_data", state)

    return aliases


def _apply_binding_adapters(
    value: Any,
    *,
    binding: Any,
    target_backend: ComputeBackend,
) -> Any:
    compatibility = binding.compatibility
    if compatibility.requires_fx_rate:
        raise MethodContractError(
            binding.target_method,
            (
                f"binding {binding.source_slot}->{binding.target_slot} requires an FX rate "
                "adapter, which is not available at execution time"
            ),
        )

    factor = compatibility.conversion_factor
    result = value
    if factor not in (None, 1.0):
        try:
            result = result * factor
        except Exception as exc:
            raise MethodContractError(
                binding.target_method,
                (
                    f"failed to apply unit conversion factor {factor!r} for binding "
                    f"{binding.source_slot}->{binding.target_slot}: {exc}"
                ),
            ) from exc

    shape_adapter = compatibility.adapter_plan.shape
    if shape_adapter.kind == ShapeAdapterKind.IDENTITY:
        return result

    array_value = np.asarray(result)
    if shape_adapter.kind == ShapeAdapterKind.BROADCAST_TO:
        target_shape = _runtime_shape(shape_adapter.target_shape, array_value.shape)
        array_value = np.broadcast_to(array_value, target_shape)
    elif shape_adapter.kind == ShapeAdapterKind.EXPAND_DIMS:
        axis = 0 if shape_adapter.axis is None else int(shape_adapter.axis)
        array_value = np.expand_dims(array_value, axis=axis)
    elif shape_adapter.kind == ShapeAdapterKind.UNSAFE_RESHAPE:
        target_shape = _runtime_shape(shape_adapter.target_shape, array_value.shape)
        array_value = np.reshape(array_value, target_shape)

    if target_backend is ComputeBackend.JAX:
        return adapt_state(
            array_value,
            source_backend=ComputeBackend.NUMPY,
            target_backend=target_backend,
        )
    return array_value


def _runtime_shape(
    target_shape: tuple[int | str, ...] | None,
    current_shape: tuple[int, ...],
) -> tuple[int, ...]:
    if target_shape is None:
        return current_shape
    if len(target_shape) != len(current_shape):
        return tuple(dim for dim in current_shape)
    resolved: list[int] = []
    for idx, dim in enumerate(target_shape):
        if isinstance(dim, int):
            resolved.append(dim)
        else:
            resolved.append(int(current_shape[idx]))
    return tuple(resolved)
