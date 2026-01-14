from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Sequence

import equinox as eqx
import jax
import jax.numpy as jnp
from pydantic import TypeAdapter

from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.registry import create_mechanism_from_spec
from polisyos.ir.kernel import (
    MechanismTypeRegistry,
    MergeRuleKind,
    MergeRuleRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
    SlotScope,
)
from polisyos.ir.surface import (
    ScheduleSpec,
    SelectorAll,
    SelectorAny,
    SelectorExpr,
    SelectorNot,
    SelectorPredicate,
    schedule_range,
)
from polisyos.ir.types import SelectorOperator


@dataclass
class PreparedNode:
    """Предкомпилированный узел графа для чистого исполнения."""

    node_id: str
    mechanism_type: str
    rank: int
    start: int
    end: int
    mechanism: Any
    outputs: list[str]
    selector: SelectorExpr | None = None
    priority: int | None = None


@dataclass
class TrainableHandle:
    """Ссылка на поле механизма, которое можно обновлять во время калибровки."""

    node_index: int
    node_id: str
    mechanism_type: str
    field_name: str
    lower: float | None
    upper: float | None
    selector: SelectorExpr | None = None
    prior_mean: float | None = None
    prior_std: float | None = None


@dataclass
class StaticBundle:
    """Все статические данные для чистого прогоняющего шага."""

    nodes: list[PreparedNode]
    slot_registry: SlotRegistry
    mechanism_registry: MechanismTypeRegistry
    merge_registry: MergeRuleRegistry
    selector_field_registry: SelectorFieldRegistry | None
    trainables: list[TrainableHandle]


def compile_program(
    program_graph: ProgramGraph,
    exec_plan: ExecPlan,
    *,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
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
    selector_adapter = TypeAdapter(SelectorExpr)
    mask_map: dict[str, SelectorExpr] = {}

    for node in program_graph.nodes:
        if node.node_kind != "op" or node.op is None:
            continue
        if node.op.op_kind != "make_mask":
            continue
        selector_payload = node.op.params.get("selector")
        if selector_payload is None:
            continue
        mask_map[node.node_id] = selector_adapter.validate_python(selector_payload)

    for node_id in order:
        node = node_map.get(node_id)
        if node is None:
            continue

        if node.node_kind not in {"mechanism", "op"}:
            continue

        mechanism_type = node.mechanism_type
        params_ref = node.params_ref
        selector = None
        mask_id = None
        if node.node_kind == "op" and node.op and node.op.op_kind == "apply_mechanism":
            mechanism_type = node.op.params.get("mechanism_type") or mechanism_type
            params_ref = node.op.params.get("params_ref") or params_ref
            selector = node.op.params.get("selector")
            mask_id = node.op.params.get("mask_id")
        if mechanism_type is None:
            continue

        payload: dict[str, Any] = {}
        if parameter_loader is not None:
            payload = parameter_loader(params_ref or node) or {}
        schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
        start, end = schedule_range(schedule)
        params = payload.get("params", {})
        priority = payload.get("priority")
        mechanism = create_mechanism_from_spec(
            mechanism_type, params, n_agents=n_agents, n_firms=n_firms
        )
        selector_payload = selector
        if selector_payload is None and mask_id in mask_map:
            selector_payload = mask_map[mask_id]
        if selector_payload is None:
            selector_payload = payload.get("target")
        selector_expr = (
            selector_adapter.validate_python(selector_payload)
            if selector_payload is not None
            else None
        )
        prepared.append(
            PreparedNode(
                node_id=node_id,
                mechanism_type=mechanism_type,
                rank=-1,
                start=int(start),
                end=int(end),
                mechanism=mechanism,
                outputs=list(node.outputs),
                selector=selector_expr,
                priority=priority,
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
                    node_id=node_id,
                    mechanism_type=mechanism_type,
                    field_name=param_key,
                    lower=lower,
                    upper=upper,
                    selector=selector_expr,
                    prior_mean=float(param_spec.prior_mean) if param_spec.prior_mean is not None else None,
                    prior_std=float(param_spec.prior_std) if param_spec.prior_std is not None else None,
                )
            )

    sorted_ids = sorted(node.node_id for node in prepared)
    rank_map = {node_id: idx for idx, node_id in enumerate(sorted_ids)}
    prepared = [replace(node, rank=rank_map.get(node.node_id, 0)) for node in prepared]

    return StaticBundle(
        nodes=prepared,
        slot_registry=slot_registry,
        mechanism_registry=mechanism_registry,
        merge_registry=merge_registry,
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


def _coerce_selector_scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lower() in {"true", "false"}:
            return text.lower() == "true"
        try:
            return float(Decimal(text))
        except InvalidOperation:
            return value
    return value


def _selector_field_values(
    state: Any,
    field_id: str,
    *,
    selector_field_registry: SelectorFieldRegistry | None,
) -> tuple[jnp.ndarray, SlotScope]:
    if field_id in {"id", "agent_id"}:
        n_agents = getattr(state.agents, "size", None)
        if n_agents is None:
            n_agents = int(state.agents.income.shape[0])
        return jnp.arange(int(n_agents)), SlotScope.PER_AGENT
    if selector_field_registry is None:
        raise ValueError(f"Selector field '{field_id}' requires registry mapping")
    spec = selector_field_registry.fields.get(field_id)
    if spec is None:
        raise ValueError(f"Unknown selector field '{field_id}'")
    if spec.state_path is None:
        raise ValueError(f"Selector field '{field_id}' missing state_path")
    return _get_state_path(state, spec.state_path), spec.scope


def _apply_operator(values: jnp.ndarray, operator: SelectorOperator, value: Any) -> jnp.ndarray:
    if isinstance(value, list):
        coerced = [_coerce_selector_scalar(item) for item in value]
    else:
        coerced = _coerce_selector_scalar(value)
    if isinstance(coerced, list):
        arr = jnp.asarray(coerced)
        if operator == SelectorOperator.IN:
            return jnp.isin(values, arr)
        if operator == SelectorOperator.NOT_IN:
            return ~jnp.isin(values, arr)
        if operator == SelectorOperator.BETWEEN and len(coerced) == 2:
            return (values >= arr[0]) & (values <= arr[1])
    if operator == SelectorOperator.EQUALS:
        return values == coerced
    if operator == SelectorOperator.NOT_EQUALS:
        return values != coerced
    if operator == SelectorOperator.GREATER_THAN:
        return values > coerced
    if operator == SelectorOperator.LESS_THAN:
        return values < coerced
    if operator == SelectorOperator.GREATER_EQUAL:
        return values >= coerced
    if operator == SelectorOperator.LESS_EQUAL:
        return values <= coerced
    if operator == SelectorOperator.CONTAINS:
        if isinstance(coerced, list):
            return jnp.isin(values, jnp.asarray(coerced))
    raise ValueError(f"Unsupported selector operator/value: {operator}")


def _evaluate_selector(
    node: SelectorExpr,
    state: Any,
    *,
    selector_field_registry: SelectorFieldRegistry | None,
) -> tuple[jnp.ndarray, SlotScope]:
    if isinstance(node, SelectorPredicate):
        values, scope = _selector_field_values(
            state, node.field, selector_field_registry=selector_field_registry
        )
        if isinstance(node.value, str) and node.value.strip().lower() in {"all", "any"}:
            return jnp.ones_like(values, dtype=bool), scope
        return _apply_operator(values, node.operator, node.value), scope
    if isinstance(node, SelectorNot):
        mask, scope = _evaluate_selector(
            node.clause, state, selector_field_registry=selector_field_registry
        )
        return ~mask, scope
    if isinstance(node, (SelectorAll, SelectorAny)):
        masks = []
        scopes: set[SlotScope] = set()
        clauses = node.clauses if isinstance(node, (SelectorAll, SelectorAny)) else []
        for clause in clauses:
            mask, scope = _evaluate_selector(
                clause, state, selector_field_registry=selector_field_registry
            )
            masks.append(mask)
            scopes.add(scope)
        if len(scopes) != 1:
            raise ValueError("Selector mixes scopes; cannot evaluate")
        scope = scopes.pop() if scopes else SlotScope.PER_AGENT
        if not masks:
            return jnp.ones(1, dtype=bool), scope
        if isinstance(node, SelectorAll):
            combined = masks[0]
            for mask in masks[1:]:
                combined = combined & mask
            return combined, scope
        combined = masks[0]
        for mask in masks[1:]:
            combined = combined | mask
        return combined, scope
    raise ValueError("Invalid selector expression")


def _apply_mask(value: jnp.ndarray, mask: jnp.ndarray) -> jnp.ndarray:
    if value.dtype == jnp.bool_:
        return jnp.where(mask, value, False)
    return jnp.where(mask, value, jnp.zeros_like(value))


def _mask_state_inputs(
    base_state: Any,
    mask: jnp.ndarray,
    mask_scope: SlotScope,
    *,
    mechanism_type: str,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
) -> Any:
    mech = mechanism_registry.mechanisms.get(mechanism_type)
    if mech is None or mask_scope not in {SlotScope.PER_AGENT, SlotScope.PER_FIRM}:
        return base_state
    state = base_state
    for slot_id in mech.reads_slots:
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            continue
        if slot_spec.scope != mask_scope:
            continue
        base_value = _get_state_path(state, slot_spec.state_path)
        masked = _apply_mask(base_value, mask)
        state = _set_state_path(state, slot_spec.state_path, masked)
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
    """Применение механизмов за один шаг с selector masks и merge rules."""
    base_state = state
    cur_key = key
    patch_records: dict[str, list[dict[str, Any]]] = {}

    for node in bundle.nodes:
        active = (t >= node.start) & (t <= node.end)
        if node.selector is not None:
            mask, mask_scope = _evaluate_selector(
                node.selector, base_state, selector_field_registry=bundle.selector_field_registry
            )
        else:
            mask = None
            mask_scope = None

        def _run(carry):
            st, k = carry
            k, sub = jax.random.split(k)
            full_state, _ = node.mechanism(st, sub)
            if mask is None:
                return full_state, full_state, k
            masked_inputs = _mask_state_inputs(
                st,
                mask,
                mask_scope,
                mechanism_type=node.mechanism_type,
                mechanism_registry=bundle.mechanism_registry,
                slot_registry=bundle.slot_registry,
            )
            masked_state, _ = node.mechanism(masked_inputs, sub)
            return full_state, masked_state, k

        def _skip(carry):
            st, k = carry
            return st, st, k

        full_state, masked_state, cur_key = jax.lax.cond(
            active,
            _run,
            _skip,
            operand=(base_state, cur_key),
        )

        for slot_id in node.outputs:
            slot_spec = bundle.slot_registry.slots.get(slot_id)
            if slot_spec is None or not slot_spec.state_path:
                raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
            base_value = _get_state_path(base_state, slot_spec.state_path)
            full_value = _get_state_path(full_state, slot_spec.state_path)
            if mask is None:
                new_value = full_value
            elif slot_spec.scope == SlotScope.GLOBAL:
                new_value = _get_state_path(masked_state, slot_spec.state_path)
            elif slot_spec.scope == mask_scope:
                new_value = jnp.where(mask, full_value, base_value)
            else:
                raise ValueError(
                    f"Selector scope '{mask_scope.value}' incompatible with slot "
                    f"'{slot_id}' ({slot_spec.scope.value})"
                )
            delta = new_value - base_value
            patch_records.setdefault(slot_id, []).append(
                {
                    "delta": delta,
                    "new_value": new_value,
                    "priority": node.priority,
                    "rank": float(node.rank),
                    "active": active,
                }
            )

    state = base_state
    for slot_id, records in sorted(patch_records.items()):
        slot_spec = bundle.slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        rule = bundle.merge_registry.rules.get(slot_spec.merge_rule.rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{slot_spec.merge_rule.rule_id}' for '{slot_id}'")
        base_value = _get_state_path(base_state, slot_spec.state_path)
        if rule.kind == MergeRuleKind.SUM:
            total_delta = None
            for record in records:
                delta = record["delta"]
                masked_delta = jnp.where(record["active"], delta, jnp.zeros_like(delta))
                total_delta = masked_delta if total_delta is None else total_delta + masked_delta
            new_value = base_value + (total_delta if total_delta is not None else 0.0)
        elif rule.kind == MergeRuleKind.OVERRIDE:
            best_rank = jnp.array(-1e9)
            new_value = base_value
            for record in records:
                rank = jnp.array(record["rank"])
                better = record["active"] & (rank > best_rank)
                new_value = jnp.where(better, record["new_value"], new_value)
                best_rank = jnp.where(better, rank, best_rank)
        elif rule.kind == MergeRuleKind.PRIORITY:
            if any(record["priority"] is None for record in records):
                raise ValueError(f"Merge rule 'priority' requires priority for slot '{slot_id}'")
            best_priority = jnp.array(-1e9)
            best_rank = jnp.array(1e9)
            new_value = base_value
            for record in records:
                priority = jnp.array(float(record["priority"]))
                rank = jnp.array(record["rank"])
                higher = priority > best_priority
                tie = (priority == best_priority) & (rank < best_rank)
                better = record["active"] & (higher | tie)
                new_value = jnp.where(better, record["new_value"], new_value)
                best_priority = jnp.where(better, priority, best_priority)
                best_rank = jnp.where(better, rank, best_rank)
        elif rule.kind == MergeRuleKind.ERROR:
            best_rank = jnp.array(1e9)
            new_value = base_value
            for record in records:
                rank = jnp.array(record["rank"])
                better = record["active"] & (rank < best_rank)
                new_value = jnp.where(better, record["new_value"], new_value)
                best_rank = jnp.where(better, rank, best_rank)
        else:
            raise ValueError(f"Unsupported merge rule '{rule.kind}' for '{slot_id}'")
        state = _set_state_path(state, slot_spec.state_path, new_value)

    return state, cur_key


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
