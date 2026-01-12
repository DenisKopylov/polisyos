from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable, Sequence

import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.registry import create_mechanism_from_spec
from polisyos.ir.kernel import MechanismTypeRegistry, SelectorFieldRegistry, SlotRegistry
from polisyos.ir.surface import ScheduleSpec, SelectorExpr, schedule_range


@dataclass
class PreparedNode:
    """Предкомпилированный узел графа для чистого исполнения."""

    node_id: str
    start: int
    end: int
    mechanism: Any
    outputs: list[str]
    selector: SelectorExpr | None = None


@dataclass
class TrainableHandle:
    """Ссылка на поле механизма, которое можно обновлять во время калибровки."""

    node_index: int
    field_name: str
    lower: float | None
    upper: float | None


@dataclass
class StaticBundle:
    """Все статические данные для чистого прогоняющего шага."""

    nodes: list[PreparedNode]
    slot_registry: SlotRegistry
    selector_field_registry: SelectorFieldRegistry | None
    trainables: list[TrainableHandle]


def compile_program(
    program_graph: ProgramGraph,
    exec_plan: ExecPlan,
    *,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
    selector_field_registry: SelectorFieldRegistry | None = None,
    base_state: GlobalState | None = None,
    parameter_loader: Callable[[Any], dict[str, Any]] | None = None,
) -> StaticBundle:
    """
    Предварительная компиляция ProgramGraph -> StaticBundle без обращений к CAS внутри JAX-цикла.

    parameter_loader: функция, которая по params_ref (или node) возвращает payload с ключами schedule/params.
    """
    order = exec_plan.order or [node.node_id for node in program_graph.nodes]
    node_map = {node.node_id: node for node in program_graph.nodes}

    n_agents = getattr(base_state.agents, "size", None) if base_state is not None else None
    if n_agents is None and base_state is not None:
        n_agents = int(base_state.agents.income.shape[0])
    n_firms = getattr(base_state.firms, "size", None) if base_state is not None else None
    if n_firms is None and base_state is not None:
        n_firms = int(base_state.firms.capital.shape[0])

    prepared: list[PreparedNode] = []
    trainables: list[TrainableHandle] = []

    for node_id in order:
        node = node_map.get(node_id)
        if node is None:
            continue

        if node.node_kind not in {"mechanism", "op"}:
            continue

        mechanism_type = node.mechanism_type
        params_ref = node.params_ref
        selector = None
        if node.node_kind == "op" and node.op and node.op.op_kind == "apply_mechanism":
            mechanism_type = node.op.params.get("mechanism_type") or mechanism_type
            params_ref = node.op.params.get("params_ref") or params_ref
            selector = node.op.params.get("selector")
        if mechanism_type is None:
            continue

        payload: dict[str, Any] = {}
        if parameter_loader is not None:
            payload = parameter_loader(params_ref or node) or {}
        schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
        start, end = schedule_range(schedule)
        params = payload.get("params", {})
        mechanism = create_mechanism_from_spec(
            mechanism_type, params, n_agents=n_agents, n_firms=n_firms
        )
        prepared.append(
            PreparedNode(
                node_id=node_id,
                start=int(start),
                end=int(end),
                mechanism=mechanism,
                outputs=list(node.outputs),
                selector=selector,
            )
        )

        mech_spec = mechanism_registry.mechanisms.get(mechanism_type)
        if mech_spec is None:
            continue
        for param_key, param_spec in mech_spec.params.items():
            if not param_spec.trainable:
                continue
            lower = float(param_spec.min_value) if param_spec.min_value is not None else None
            upper = float(param_spec.max_value) if param_spec.max_value is not None else None
            trainables.append(
                TrainableHandle(
                    node_index=len(prepared) - 1,
                    field_name=param_key,
                    lower=lower,
                    upper=upper,
                )
            )

    return StaticBundle(
        nodes=prepared,
        slot_registry=slot_registry,
        selector_field_registry=selector_field_registry,
        trainables=trainables,
    )


def _get_state_path(obj: Any, path: str) -> Any:
    current = obj
    for part in path.split("."):
        current = getattr(current, part)
    return current


def _set_state_path(obj: Any, path: str, value: Any) -> Any:
    parts = path.split(".")
    if len(parts) == 1:
        return obj.replace(**{parts[0]: value})
    head, tail = parts[0], parts[1:]
    child = getattr(obj, head)
    updated = _set_state_path(child, ".".join(tail), value)
    return obj.replace(**{head: updated})


def _apply_outputs(base_state: GlobalState, full_state: GlobalState, outputs: Iterable[str], slot_registry: SlotRegistry) -> GlobalState:
    state = base_state
    for slot_id in outputs:
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            continue
        new_value = _get_state_path(full_state, slot_spec.state_path)
        state = _set_state_path(state, slot_spec.state_path, new_value)
    return state


def apply_trainable_values(bundle: StaticBundle, values: Sequence[Any]) -> StaticBundle:
    """Вернуть копию bundle с обновлёнными trainable полями механизмов."""
    if not bundle.trainables:
        return bundle
    updated_nodes = list(bundle.nodes)
    for handle, value in zip(bundle.trainables, values):
        node = updated_nodes[handle.node_index]
        mech = eqx.tree_at(lambda m: getattr(m, handle.field_name), node.mechanism, value)
        updated_nodes[handle.node_index] = replace(node, mechanism=mech)
    return replace(bundle, nodes=updated_nodes)


def extract_trainable_values(bundle: StaticBundle) -> list[Any]:
    values: list[Any] = []
    for handle in bundle.trainables:
        mech = bundle.nodes[handle.node_index].mechanism
        values.append(getattr(mech, handle.field_name))
    return values


def apply_nodes(
    state: GlobalState,
    key: jax.Array,
    *,
    bundle: StaticBundle,
    t: jax.Array,
) -> tuple[GlobalState, jax.Array]:
    """Последовательное применение механизмов за один шаг."""
    current = state
    cur_key = key

    for node in bundle.nodes:
        active = (t >= node.start) & (t <= node.end)

        def _run(carry):
            st, k = carry
            k, sub = jax.random.split(k)
            next_state, _ = node.mechanism(st, sub)
            updated = (
                _apply_outputs(st, next_state, node.outputs, bundle.slot_registry)
                if node.outputs
                else next_state
            )
            return updated, k

        current, cur_key = jax.lax.cond(
            active,
            _run,
            lambda carry: carry,
            operand=(current, cur_key),
        )

    return current, cur_key


def run_pure_scan(
    initial_state: GlobalState,
    *,
    steps: int,
    root_key: jax.Array,
    bundle: StaticBundle,
    metric_paths: Sequence[str] | None = None,
    controls_seq: jnp.ndarray | None = None,
):
    """
    Чистый прогон симуляции через lax.scan без IO.
    Возвращает PyTree трасс, где ключи = metric_paths (если заданы).
    """
    metric_paths = tuple(metric_paths or ())
    seq = controls_seq if controls_seq is not None else jnp.arange(steps)

    def _body(carry, _):
        state, key, t = carry
        next_state, next_key = apply_nodes(state, key, bundle=bundle, t=t)
        metrics = {path: _get_state_path(next_state, path) for path in metric_paths}
        return (next_state, next_key, t + 1), metrics

    (final_state, _, _), traces = jax.lax.scan(
        _body,
        (initial_state, root_key, jnp.array(0, dtype=jnp.int32)),
        seq,
    )
    return final_state, traces
