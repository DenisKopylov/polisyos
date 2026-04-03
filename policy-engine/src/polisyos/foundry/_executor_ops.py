"""Selector evaluation, constraint checking, and patch-op application."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

import jax.numpy as jnp
import numpy as np

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import LoweredConstraint, PatchOp
from polisyos.ir.governance.selector_expr import (
    SelectorAll,
    SelectorAny,
    SelectorExpr,
    SelectorNot,
    SelectorPredicate,
)
from polisyos.ir.kernel import (
    ConstraintRegistry,
    MergeRuleKind,
    MergeRuleRegistry,
    SelectorFieldRegistry,
    SlotRegistry,
    SlotScope,
)
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.ir.types import SelectorOperator

from ._executor_models import get_state_path, load_tensor, set_state_path
from .constraints_engine import check_constraints as evaluate_lowered_constraints

__all__ = [
    "coerce_selector_scalar",
    "selector_field_values",
    "apply_operator",
    "evaluate_selector",
    "apply_ops_to_state",
    "coerce_number",
    "check_constraints",
    "validate_ops_compatibility",
    "apply_ops_for_slot",
    "apply_op",
]


# ---------------------------------------------------------------------------
# Selector helpers
# ---------------------------------------------------------------------------


def coerce_selector_scalar(value: Any) -> Any:
    """Coerce selector scalar helper."""
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


def selector_field_values(
    state: Any,
    field_id: str,
    *,
    selector_field_registry: SelectorFieldRegistry | None,
) -> tuple[jnp.ndarray, SlotScope]:
    """Selector field values helper."""
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
    return get_state_path(state, spec.state_path), spec.scope


def apply_operator(values: jnp.ndarray, operator: SelectorOperator, value: Any) -> jnp.ndarray:
    """Apply operator helper."""
    if isinstance(value, list):
        coerced = [coerce_selector_scalar(item) for item in value]
    else:
        coerced = coerce_selector_scalar(value)
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


def evaluate_selector(
    node: SelectorExpr,
    state: Any,
    *,
    selector_field_registry: SelectorFieldRegistry | None,
) -> tuple[jnp.ndarray, SlotScope]:
    """Evaluate selector helper."""
    if isinstance(node, SelectorPredicate):
        values, scope = selector_field_values(
            state, node.field, selector_field_registry=selector_field_registry
        )
        if isinstance(node.value, str) and node.value.strip().lower() in {"all", "any"}:
            return jnp.ones_like(values, dtype=bool), scope
        return apply_operator(values, node.operator, node.value), scope
    if isinstance(node, SelectorNot):
        mask, scope = evaluate_selector(
            node.clause, state, selector_field_registry=selector_field_registry
        )
        return ~mask, scope
    if isinstance(node, (SelectorAll, SelectorAny)):
        masks = []
        scopes: set[SlotScope] = set()
        clauses = node.clauses if isinstance(node, (SelectorAll, SelectorAny)) else []
        for clause in clauses:
            mask, scope = evaluate_selector(
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


# ---------------------------------------------------------------------------
# Constraint checking
# ---------------------------------------------------------------------------


def coerce_number(value: Any) -> Decimal | None:
    """Coerce number helper."""
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


def check_constraints(
    constraint_ids: list[Any],
    *,
    constraint_registry: ConstraintRegistry,
    constraint_values: dict[str, Any],
    slot_registry: SlotRegistry,
    state: Any,
    events: list[dict[str, Any]] | None = None,
) -> Any:
    """Check constraints helper."""
    lowered_constraints: list[LoweredConstraint] = []
    for constraint_id in constraint_ids:
        if not isinstance(constraint_id, str):
            continue
        spec = constraint_registry.constraints.get(constraint_id)
        if spec is None or spec.slot_id is None or spec.operator is None:
            continue
        value = constraint_values.get(constraint_id)
        if value is None:
            raise ValueError(f"Constraint '{constraint_id}' missing value in policy")
        numeric = coerce_number(value)
        if numeric is None:
            raise ValueError(f"Constraint '{constraint_id}' has non-numeric value")
        lowered_constraints.append(
            LoweredConstraint(
                constraint_id=constraint_id,
                severity="hard",
                slot_id=spec.slot_id,
                operator=spec.operator,
                expected=str(numeric),
                unit_id=spec.unit_id,
            )
        )

    report = evaluate_lowered_constraints(
        constraints=lowered_constraints,
        slot_registry=slot_registry,
        state=state,
    )
    if events is not None:
        for verdict in report.violations:
            events.extend(verdict.events)
    if report.hard_fail:
        failed = next((item for item in report.violations if item.violated), None)
        if failed is not None:
            raise ValueError(
                f"Constraint '{failed.constraint_id}' violated: "
                f"{failed.actual} vs {failed.operator} {failed.expected}"
            )
        raise ValueError("Hard constraint violated")
    return report


# ---------------------------------------------------------------------------
# Patch-op validation and application
# ---------------------------------------------------------------------------


def validate_ops_compatibility(
    slot_id: str, rule_kind: MergeRuleKind, ops: Iterable[PatchOp]
) -> None:
    """Validate ops compatibility."""
    for op in ops:
        if op.op == "add" and rule_kind != MergeRuleKind.SUM:
            raise ValueError(f"Patch op 'add' incompatible with merge rule for '{slot_id}'")
        if op.op == "set" and rule_kind == MergeRuleKind.SUM:
            raise ValueError(f"Patch op 'set' incompatible with merge rule for '{slot_id}'")


def apply_ops_for_slot(store: FileSystemCAS, base_value: Any, ops: Iterable[PatchOp]) -> Any:
    """Apply ops for slot helper."""
    ops_list = list(ops)
    if not ops_list:
        return base_value
    if len(ops_list) == 1:
        return apply_op(store, base_value, ops_list[0])
    if all(op.op == "add" for op in ops_list):
        total = None
        for op in ops_list:
            if op.value_ref is None:
                raise ValueError(f"Patch op 'add' missing value_ref for slot '{op.slot_id}'")
            value = jnp.asarray(load_tensor(store, op.value_ref))
            if op.mask_ref is not None:
                mask = jnp.asarray(load_tensor(store, op.mask_ref)).astype(bool)
                value = jnp.where(mask, value, jnp.asarray(0))
            total = value if total is None else total + value
        return base_value + (total if total is not None else jnp.asarray(0))
    raise ValueError("Multiple patch ops for a slot are not supported")


def apply_op(store: FileSystemCAS, base_value: Any, op: PatchOp) -> Any:
    """Apply op helper."""
    if op.value_ref is None:
        raise ValueError(f"Patch op '{op.op}' missing value_ref for slot '{op.slot_id}'")
    value = jnp.asarray(load_tensor(store, op.value_ref))
    if op.mask_ref is not None:
        mask = jnp.asarray(load_tensor(store, op.mask_ref)).astype(bool)
        if op.op == "add":
            value = jnp.where(mask, value, jnp.asarray(0))
        elif op.op == "set":
            return jnp.where(mask, value, base_value)
    if op.op == "add":
        return base_value + value
    if op.op == "set":
        return value
    raise ValueError(f"Unsupported patch op '{op.op}'")


def apply_ops_to_state(
    store: FileSystemCAS,
    *,
    base_state: Any,
    ops: Iterable[PatchOp],
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> Any:
    """Apply ops to state helper."""
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
        validate_ops_compatibility(slot_id, rule.kind, slot_ops)
        base_value = get_state_path(state, slot_spec.state_path)
        merged = apply_ops_for_slot(store, base_value, slot_ops)
        state = set_state_path(state, slot_spec.state_path, merged)
    return state
