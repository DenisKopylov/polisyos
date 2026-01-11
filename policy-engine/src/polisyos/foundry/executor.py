from __future__ import annotations

from dataclasses import dataclass
import dataclasses
from io import BytesIO
from typing import Any, Iterable

import jax
import jax.numpy as jnp
import numpy as np
from decimal import Decimal, InvalidOperation
from pydantic import BaseModel, TypeAdapter

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ExecPlan,
    Metrics,
    PatchOp,
    ProgramGraph,
    StateDelta,
    StateSnapshot,
)
from polisyos.foundry.registry import create_mechanism_from_spec
from polisyos.foundry.domain.state import GlobalState
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MechanismTypeRegistry,
    MergeRuleKind,
    MergeRuleRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
    SlotScope,
)
from polisyos.ir.surface import (
    PolicySurfaceIR,
    ScheduleSpec,
    SelectorAll,
    SelectorAny,
    SelectorExpr,
    SelectorNot,
    SelectorPredicate,
    schedule_range,
)
from polisyos.ir.types import SelectorOperator
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue


@dataclass(frozen=True)
class ExecuteArtifacts:
    state_delta_ref: ArtifactRef
    metrics_ref: ArtifactRef


@dataclass(frozen=True)
class ApplyArtifacts:
    state_snapshot_ref: ArtifactRef


_SELECTOR_ADAPTER = TypeAdapter(SelectorExpr)


def execute_program_graph(
    store: FileSystemCAS,
    *,
    program_ref: ArtifactRef | ArtifactID | str,
    exec_plan_ref: ArtifactRef | ArtifactID | str,
    base_state: Any,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    selector_field_registry: SelectorFieldRegistry | None = None,
    constraint_registry: ConstraintRegistry | None = None,
    step: int = 0,
    seed: int = 0,
    base_ref: ArtifactRef | None = None,
) -> ExecuteArtifacts:
    program_graph = _load_model(store, program_ref, ProgramGraph)
    exec_plan = _load_model(store, exec_plan_ref, ExecPlan)

    order = exec_plan.order or [node.node_id for node in program_graph.nodes]
    node_map = {node.node_id: node for node in program_graph.nodes}

    n_agents = getattr(base_state.agents, "size", None)
    if n_agents is None:
        n_agents = int(base_state.agents.income.shape[0])
    n_firms = getattr(base_state.firms, "size", None)
    if n_firms is None:
        n_firms = int(base_state.firms.capital.shape[0])

    key = jax.random.PRNGKey(seed)
    patch_records: dict[str, list[dict[str, Any]]] = {}
    ops: list[PatchOp] = []
    applied_nodes = 0
    skipped_nodes = 0
    op_nodes = 0
    checked_constraints = 0
    masks: dict[str, tuple[jnp.ndarray, SlotScope]] = {}
    state_for_checks = base_state

    constraint_values: dict[str, Any] = {}
    if constraint_registry is not None:
        try:
            policy_payload = from_canonical_bytes(
                store.get_bytes(program_graph.ir_ref.artifact_id)
            )
            policy = PolicySurfaceIR.model_validate(policy_payload)
            constraint_values = {
                constraint.constraint_id: constraint.value
                for constraint in policy.semantic.constraints
            }
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"Failed to load policy for constraints: {exc}") from exc

    for node_id in order:
        node = node_map.get(node_id)
        if node is None:
            skipped_nodes += 1
            continue
        if node.node_kind == "op":
            op_nodes += 1
            if node.op is None:
                skipped_nodes += 1
                continue
            if node.op.op_kind == "make_mask":
                selector_payload = node.op.params.get("selector") or {}
                target = _SELECTOR_ADAPTER.validate_python(selector_payload)
                mask, scope = _evaluate_selector(
                    target, base_state, selector_field_registry=selector_field_registry
                )
                masks[node.node_id] = (mask, scope)
                continue
            if node.op.op_kind == "apply_mechanism":
                if node.params_ref is None:
                    skipped_nodes += 1
                    continue
                payload = _load_payload(store, node.params_ref)
                schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
                start, end = schedule_range(schedule)
                if step < start or step > end:
                    skipped_nodes += 1
                    continue

                mask_info = None
                mask_id = node.op.params.get("mask_id")
                if isinstance(mask_id, str):
                    mask_info = masks.get(mask_id)
                if mask_info is None:
                    selector_payload = payload.get("target") or {}
                    target = _SELECTOR_ADAPTER.validate_python(selector_payload)
                    mask_info = _evaluate_selector(
                        target, base_state, selector_field_registry=selector_field_registry
                    )
                mask, mask_scope = mask_info

                params = payload.get("params", {})
                mechanism_type = node.mechanism_type
                mechanism = create_mechanism_from_spec(
                    mechanism_type, params, n_agents=n_agents, n_firms=n_firms
                )
                key, step_key = jax.random.split(key)

                patch_map = None
                if hasattr(mechanism, "emit_patches"):
                    patch_map, key = mechanism.emit_patches(
                        base_state,
                        step_key,
                        target_mask=mask
                        if mask_scope in {SlotScope.PER_AGENT, SlotScope.PER_FIRM}
                        else None,
                    )
                if patch_map:
                    applied_nodes += 1
                    for slot_id, patch in patch_map.items():
                        record = {
                            "node_id": node_id,
                            "priority": payload.get("priority"),
                        }
                        record.update(patch)
                        patch_records.setdefault(slot_id, []).append(record)
                    continue

                full_state, key = mechanism(base_state, step_key)
                masked_state = full_state
                mask_all = _mask_is_all(mask)
                if not mask_all:
                    masked_input_state = _mask_state_inputs(
                        base_state,
                        mask,
                        mask_scope,
                        mechanism_type=mechanism_type,
                        mechanism_registry=mechanism_registry,
                        slot_registry=slot_registry,
                    )
                    masked_state, key = mechanism(masked_input_state, step_key)

                applied_nodes += 1
                for slot_id in node.outputs:
                    slot_spec = slot_registry.slots.get(slot_id)
                    if slot_spec is None or not slot_spec.state_path:
                        raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
                    base_value = _get_state_path(base_state, slot_spec.state_path)
                    full_value = _get_state_path(full_state, slot_spec.state_path)
                    if mask_all:
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
                    patch_records.setdefault(slot_id, []).append(
                        {
                            "node_id": node_id,
                            "priority": payload.get("priority"),
                            "base_value": base_value,
                            "new_value": new_value,
                            "delta": new_value - base_value,
                        }
                    )
                continue
            if node.op.op_kind == "merge_state":
                ops = _merge_patch_records(
                    store,
                    patch_records,
                    slot_registry=slot_registry,
                    merge_registry=merge_registry,
                )
                patch_records = {}
                if constraint_registry is not None:
                    state_for_checks = _apply_ops_to_state(
                        store,
                        base_state=base_state,
                        ops=ops,
                        slot_registry=slot_registry,
                        merge_registry=merge_registry,
                    )
            elif node.op.op_kind == "check_constraints":
                ids = node.op.params.get("constraint_ids") or []
                if isinstance(ids, list):
                    checked_constraints += len(ids)
                if constraint_registry is not None:
                    _check_constraints(
                        ids,
                        constraint_registry=constraint_registry,
                        constraint_values=constraint_values,
                        slot_registry=slot_registry,
                        state=state_for_checks,
                    )
            else:
                skipped_nodes += 1
            continue
        if node.node_kind == "mechanism":
            if node.params_ref is None:
                skipped_nodes += 1
                continue
            payload = _load_payload(store, node.params_ref)
            schedule = ScheduleSpec.model_validate(payload.get("schedule", {}))
            start, end = schedule_range(schedule)
            if step < start or step > end:
                skipped_nodes += 1
                continue
            params = payload.get("params", {})
            mechanism_type = node.mechanism_type
            mechanism = create_mechanism_from_spec(
                mechanism_type, params, n_agents=n_agents, n_firms=n_firms
            )
            key, step_key = jax.random.split(key)
            next_state, key = mechanism(base_state, step_key)
            applied_nodes += 1
            for slot_id in node.outputs:
                slot_spec = slot_registry.slots.get(slot_id)
                if slot_spec is None or not slot_spec.state_path:
                    raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
                base_value = _get_state_path(base_state, slot_spec.state_path)
                new_value = _get_state_path(next_state, slot_spec.state_path)
                patch_records.setdefault(slot_id, []).append(
                    {
                        "node_id": node_id,
                        "priority": payload.get("priority"),
                        "base_value": base_value,
                        "new_value": new_value,
                        "delta": new_value - base_value,
                    }
                )
            continue
        skipped_nodes += 1

    if patch_records:
        ops = _merge_patch_records(
            store,
            patch_records,
            slot_registry=slot_registry,
            merge_registry=merge_registry,
        )

    inputs = [
        InputRef(artifact_id=_artifact_id(program_ref), role="program_graph"),
        InputRef(artifact_id=_artifact_id(exec_plan_ref), role="exec_plan"),
    ]
    for op in ops:
        if op.value_ref is not None:
            inputs.append(InputRef(artifact_id=op.value_ref.artifact_id, role="patch_value"))

    state_delta = StateDelta(base_ref=base_ref, ops=ops)
    state_delta_ref = store.put_json(
        state_delta,
        PutOptions(
            kind="foundry.state_delta",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.StateDelta", version="0.1.0"),
            inputs=inputs,
        ),
    )

    metrics = Metrics(
        values={
            "applied_nodes": int(applied_nodes),
            "skipped_nodes": int(skipped_nodes),
            "op_nodes": int(op_nodes),
            "checked_constraints": int(checked_constraints),
            "patch_ops": int(len(ops)),
            "step": int(step),
        }
    )
    metrics_ref = store.put_json(
        metrics,
        PutOptions(
            kind="foundry.metrics",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.Metrics", version="0.1.0"),
            inputs=inputs,
        ),
    )

    return ExecuteArtifacts(state_delta_ref=state_delta_ref, metrics_ref=metrics_ref)


def apply_state_delta(
    store: FileSystemCAS,
    *,
    base_state: Any,
    state_delta_ref: ArtifactRef | ArtifactID | str,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> Any:
    state_delta = _load_model(store, state_delta_ref, StateDelta)
    ops_by_slot: dict[str, list[PatchOp]] = {}
    for op in state_delta.ops:
        ops_by_slot.setdefault(op.slot_id, []).append(op)

    state = base_state
    for slot_id, ops in sorted(ops_by_slot.items()):
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        rule = merge_registry.rules.get(slot_spec.merge_rule.rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{slot_spec.merge_rule.rule_id}' for '{slot_id}'")
        _validate_ops_compatibility(slot_id, rule.kind, ops)

        base_value = _get_state_path(state, slot_spec.state_path)
        merged = _apply_ops_for_slot(store, base_value, ops)
        state = _set_state_path(state, slot_spec.state_path, merged)

    return state


def apply_state_delta_and_snapshot(
    store: FileSystemCAS,
    *,
    base_state: Any,
    state_delta_ref: ArtifactRef | ArtifactID | str,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    step: int | None = None,
    base_ref: ArtifactRef | None = None,
) -> tuple[Any, ApplyArtifacts]:
    state = apply_state_delta(
        store,
        base_state=base_state,
        state_delta_ref=state_delta_ref,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
    )
    snapshot_ref = put_state_snapshot(
        store,
        state=state,
        step=step,
        inputs=[
            InputRef(artifact_id=_artifact_id(state_delta_ref), role="state_delta"),
        ]
        + (
            [InputRef(artifact_id=base_ref.artifact_id, role="base_state")]
            if base_ref is not None
            else []
        ),
    )
    return state, ApplyArtifacts(state_snapshot_ref=snapshot_ref)


def load_state_snapshot(
    store: FileSystemCAS, *, snapshot_ref: ArtifactRef | ArtifactID | str
) -> GlobalState:
    snapshot = _load_model(store, snapshot_ref, StateSnapshot)
    data = store.get_bytes(snapshot.state_ref.artifact_id)
    blob = np.load(BytesIO(data))
    flat = {key: blob[key] for key in blob.files}
    nested = _nest_state(flat)
    return _build_dataclass(GlobalState, nested)


def _mask_is_all(mask: jnp.ndarray | None) -> bool:
    if mask is None:
        return True
    return bool(np.all(np.asarray(mask)))


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


def _apply_ops_to_state(
    store: FileSystemCAS,
    *,
    base_state: Any,
    ops: Iterable[PatchOp],
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> Any:
    ops_by_slot: dict[str, list[PatchOp]] = {}
    for op in ops:
        ops_by_slot.setdefault(op.slot_id, []).append(op)
    state = base_state
    for slot_id, slot_ops in sorted(ops_by_slot.items()):
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        rule = merge_registry.rules.get(slot_spec.merge_rule.rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{slot_spec.merge_rule.rule_id}' for '{slot_id}'")
        _validate_ops_compatibility(slot_id, rule.kind, slot_ops)
        base_value = _get_state_path(state, slot_spec.state_path)
        merged = _apply_ops_for_slot(store, base_value, slot_ops)
        state = _set_state_path(state, slot_spec.state_path, merged)
    return state


def _coerce_number(value: Any) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return None
    if isinstance(value, MoneyValue):
        return value.amount
    if isinstance(value, RateValue):
        return value.as_ratio()
    if isinstance(value, CountValue):
        return Decimal(value.value)
    if isinstance(value, DurationValue):
        return Decimal(value.value)
    return None


def _check_constraints(
    constraint_ids: list[Any],
    *,
    constraint_registry: ConstraintRegistry,
    constraint_values: dict[str, Any],
    slot_registry: SlotRegistry,
    state: Any,
) -> None:
    for constraint_id in constraint_ids:
        if not isinstance(constraint_id, str):
            continue
        spec = constraint_registry.constraints.get(constraint_id)
        if spec is None or spec.slot_id is None or spec.operator is None:
            continue
        value = constraint_values.get(constraint_id)
        if value is None:
            raise ValueError(f"Constraint '{constraint_id}' missing value in policy")
        numeric = _coerce_number(value)
        if numeric is None:
            raise ValueError(f"Constraint '{constraint_id}' has non-numeric value")
        slot_spec = slot_registry.slots.get(spec.slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Constraint '{constraint_id}' references unknown slot '{spec.slot_id}'")
        state_value = _get_state_path(state, slot_spec.state_path)
        if np.ndim(state_value) != 0:
            raise ValueError(f"Constraint '{constraint_id}' expects scalar slot value")
        current = Decimal(str(float(state_value)))
        if spec.operator == ">=" and current < numeric:
            raise ValueError(
                f"Constraint '{constraint_id}' violated: {current} < {numeric}"
            )
        if spec.operator == ">" and current <= numeric:
            raise ValueError(
                f"Constraint '{constraint_id}' violated: {current} <= {numeric}"
            )
        if spec.operator == "<=" and current > numeric:
            raise ValueError(
                f"Constraint '{constraint_id}' violated: {current} > {numeric}"
            )
        if spec.operator == "<" and current >= numeric:
            raise ValueError(
                f"Constraint '{constraint_id}' violated: {current} >= {numeric}"
            )
        if spec.operator == "==" and current != numeric:
            raise ValueError(
                f"Constraint '{constraint_id}' violated: {current} != {numeric}"
            )
        if spec.operator == "!=" and current == numeric:
            raise ValueError(
                f"Constraint '{constraint_id}' violated: {current} == {numeric}"
            )


def _artifact_id(value: ArtifactRef | ArtifactID | str) -> ArtifactID:
    if isinstance(value, ArtifactRef):
        return value.artifact_id
    if isinstance(value, ArtifactID):
        return value
    return ArtifactID.model_validate(value)


def _load_model(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str, model_cls):
    data = store.get_bytes(_artifact_id(ref))
    payload = from_canonical_bytes(data)
    return model_cls.model_validate(payload)


def _load_payload(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str) -> dict[str, Any]:
    data = store.get_bytes(_artifact_id(ref))
    payload = from_canonical_bytes(data)
    if isinstance(payload, BaseModel):
        return payload.model_dump()
    if isinstance(payload, dict):
        return payload
    raise ValueError("Invalid intervention payload")


def _put_tensor(store: FileSystemCAS, value: Any) -> ArtifactRef:
    array = np.asarray(value)
    buf = BytesIO()
    np.save(buf, array, allow_pickle=False)
    data = buf.getvalue()
    return store.put_bytes(
        data,
        PutOptions(kind="foundry.patch_value", media_type="application/x-npy"),
    )


def _load_tensor(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str) -> np.ndarray:
    data = store.get_bytes(_artifact_id(ref))
    return np.load(BytesIO(data), allow_pickle=False)


def _merge_patch_records(
    store: FileSystemCAS,
    patch_records: dict[str, list[dict[str, Any]]],
    *,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> list[PatchOp]:
    ops: list[PatchOp] = []
    for slot_id, records in sorted(patch_records.items()):
        slot_spec = slot_registry.slots.get(slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(f"Slot '{slot_id}' missing state_path for execution")
        rule = merge_registry.rules.get(slot_spec.merge_rule.rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{slot_spec.merge_rule.rule_id}' for '{slot_id}'")

        if rule.kind == MergeRuleKind.SUM:
            total_delta = None
            for record in records:
                delta = record.get("delta")
                if delta is None and "new_value" in record and "base_value" in record:
                    delta = record["new_value"] - record["base_value"]
                if delta is None:
                    raise ValueError(f"Missing delta for sum merge on slot '{slot_id}'")
                total_delta = delta if total_delta is None else total_delta + delta
            patch_value = total_delta if total_delta is not None else 0
            op = "add"
        elif rule.kind == MergeRuleKind.OVERRIDE:
            picked = sorted(records, key=lambda item: item["node_id"])[-1]
            patch_value = picked.get("value", picked.get("new_value"))
            if patch_value is None:
                raise ValueError(
                    f"Missing value for override merge on slot '{slot_id}'"
                )
            op = "set"
        elif rule.kind == MergeRuleKind.PRIORITY:
            missing = [item["node_id"] for item in records if item.get("priority") is None]
            if missing:
                raise ValueError(
                    f"Merge rule 'priority' requires priority for: {', '.join(sorted(missing))}"
                )
            picked = sorted(
                records,
                key=lambda item: (-int(item["priority"]), item["node_id"]),
            )[0]
            patch_value = picked.get("value", picked.get("new_value"))
            if patch_value is None:
                raise ValueError(
                    f"Missing value for priority merge on slot '{slot_id}'"
                )
            op = "set"
        elif rule.kind == MergeRuleKind.ERROR:
            if len(records) > 1:
                ids = ", ".join(sorted(item["node_id"] for item in records))
                raise ValueError(f"Merge conflict for slot '{slot_id}': {ids}")
            patch_value = records[0].get("value", records[0].get("new_value"))
            if patch_value is None:
                raise ValueError(f"Missing value for error merge on slot '{slot_id}'")
            op = "set"
        else:
            raise ValueError(f"Unsupported merge rule '{rule.kind}' for '{slot_id}'")

        value_ref = _put_tensor(store, patch_value)
        ops.append(
            PatchOp(
                slot_id=slot_id,
                op=op,
                value_ref=value_ref,
                notes=[f"merge:{rule.kind.value}"],
            )
        )
    return ops


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


def _apply_ops_for_slot(
    store: FileSystemCAS, base_value: Any, ops: Iterable[PatchOp]
) -> Any:
    ops_list = list(ops)
    if not ops_list:
        return base_value
    if len(ops_list) == 1:
        return _apply_op(store, base_value, ops_list[0])
    if all(op.op == "add" for op in ops_list):
        total = None
        for op in ops_list:
            if op.value_ref is None:
                raise ValueError(f"Patch op 'add' missing value_ref for slot '{op.slot_id}'")
            value = jnp.asarray(_load_tensor(store, op.value_ref))
            if op.mask_ref is not None:
                mask = jnp.asarray(_load_tensor(store, op.mask_ref)).astype(bool)
                value = jnp.where(mask, value, jnp.asarray(0))
            total = value if total is None else total + value
        return base_value + (total if total is not None else jnp.asarray(0))
    raise ValueError("Multiple patch ops for a slot are not supported")


def _apply_op(store: FileSystemCAS, base_value: Any, op: PatchOp) -> Any:
    if op.value_ref is None:
        raise ValueError(f"Patch op '{op.op}' missing value_ref for slot '{op.slot_id}'")
    value = jnp.asarray(_load_tensor(store, op.value_ref))
    if op.mask_ref is not None:
        mask = jnp.asarray(_load_tensor(store, op.mask_ref)).astype(bool)
        if op.op == "add":
            value = jnp.where(mask, value, jnp.asarray(0))
        elif op.op == "set":
            return jnp.where(mask, value, base_value)
    if op.op == "add":
        return base_value + value
    if op.op == "set":
        return value
    raise ValueError(f"Unsupported patch op '{op.op}'")


def put_state_snapshot(
    store: FileSystemCAS,
    *,
    state: Any,
    step: int | None = None,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    flat = dict(_flatten_state(state))
    buf = BytesIO()
    np.savez(buf, **flat)
    blob_ref = store.put_bytes(
        buf.getvalue(),
        PutOptions(kind="foundry.state_blob", media_type="application/x-npz", inputs=inputs),
    )
    snapshot = StateSnapshot(state_ref=blob_ref, step=step)
    snapshot_inputs = list(inputs or [])
    snapshot_inputs.append(InputRef(artifact_id=blob_ref.artifact_id, role="state_blob"))
    return store.put_json(
        snapshot,
        PutOptions(
            kind="foundry.state_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="0.1.0"),
            inputs=snapshot_inputs,
        ),
    )


def _validate_ops_compatibility(
    slot_id: str, rule_kind: MergeRuleKind, ops: Iterable[PatchOp]
) -> None:
    for op in ops:
        if op.op == "add" and rule_kind != MergeRuleKind.SUM:
            raise ValueError(f"Patch op 'add' incompatible with merge rule for '{slot_id}'")
        if op.op == "set" and rule_kind == MergeRuleKind.SUM:
            raise ValueError(f"Patch op 'set' incompatible with merge rule for '{slot_id}'")


def _flatten_state(obj: Any, prefix: str = "") -> Iterable[tuple[str, np.ndarray]]:
    if dataclasses.is_dataclass(obj):
        for field in dataclasses.fields(obj):
            name = field.name
            value = getattr(obj, name)
            yield from _flatten_state(value, f"{prefix}{name}.")
        return
    if isinstance(obj, (jax.Array, np.ndarray)):
        key = prefix[:-1]
        yield key, np.asarray(obj)
        return


def _nest_state(flat: dict[str, np.ndarray]) -> dict[str, Any]:
    nested: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(".")
        current = nested
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return nested


def _build_dataclass(cls, data: dict[str, Any]) -> Any:
    if not dataclasses.is_dataclass(cls):
        raise ValueError(f"Expected dataclass type, got: {cls}")
    kwargs: dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        value = data.get(field.name)
        if dataclasses.is_dataclass(field.type):
            if not isinstance(value, dict):
                raise ValueError(f"Missing nested data for '{field.name}'")
            kwargs[field.name] = _build_dataclass(field.type, value)
        else:
            if value is None:
                raise ValueError(f"Missing value for '{field.name}'")
            kwargs[field.name] = jnp.asarray(value)
    return cls(**kwargs)
    if isinstance(obj, (int, float, bool, np.generic)):
        key = prefix[:-1]
        yield key, np.asarray(obj)
        return
