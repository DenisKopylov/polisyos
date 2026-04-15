"""Public foundry constraints engine module API."""
from __future__ import annotations

import ast
import operator as op_module
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Iterable

import numpy as np

from polisyos.core.contracts.foundry import (
    CompositeConstraint,
    ConstraintReport,
    ConstraintViolation,
    LoweredConstraint,
)
from polisyos.ir.kernel import SlotRegistry
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue

from ._numeric import decimal_from_numeric, require_finite_numpy, validate_quantile
from ._executor_models import get_state_path


class AggregationFunction(str, Enum):
    """Aggregation for vector/tensor slots before comparison."""

    SCALAR = "scalar"
    MIN = "min"
    MAX = "max"
    MEAN = "mean"
    MEDIAN = "median"
    SUM = "sum"
    ALL = "all"
    ANY = "any"
    QUANTILE = "quantile"
    WEIGHTED_MEAN = "weighted_mean"
    COUNT_VIOLATING = "count_violating"


def check_constraints(
    *,
    constraints: Iterable[LoweredConstraint],
    slot_registry: SlotRegistry,
    state: Any,
) -> ConstraintReport:
    """Check constraints helper."""
    verdicts: list[ConstraintViolation] = []
    hard_fail = False
    penalty_total = Decimal("0")
    penalty_seen = False
    total_constraints = 0

    for constraint in constraints:
        total_constraints += 1
        slot_spec = slot_registry.slots.get(constraint.slot_id)
        if slot_spec is None or not slot_spec.state_path:
            raise ValueError(
                f"Constraint '{constraint.constraint_id}' references unknown slot '{constraint.slot_id}'"
            )

        expected = _coerce_number(constraint.expected)
        if expected is None:
            raise ValueError(f"Constraint '{constraint.constraint_id}' has non-numeric value")

        state_value = get_state_path(state, slot_spec.state_path)
        aggregation = AggregationFunction(constraint.aggregation)
        extra_events: list[dict[str, Any]] = []

        if np.ndim(state_value) == 0:
            actual = decimal_from_numeric(state_value, label=f"constraint '{constraint.constraint_id}' actual")
            violated_override = None
        else:
            actual, extra_events, violated_override = _aggregate(
                state_value,
                aggregation,
                constraint,
                expected,
                slot_registry=slot_registry,
                state=state,
            )

        if violated_override is None:
            violated = _is_violated(constraint.operator, current=actual, expected=expected)
        else:
            violated = violated_override

        penalty = None
        if violated and constraint.severity == "soft" and constraint.penalty is not None:
            penalty = constraint.penalty
            penalty_total += penalty
            penalty_seen = True
        if violated and constraint.severity == "hard":
            hard_fail = True

        events: list[dict[str, Any]] = [
            {
                "event": "constraint_evaluated",
                "constraint_id": constraint.constraint_id,
                "slot_id": constraint.slot_id,
                "ok": not violated,
            }
        ]
        events.extend(extra_events)

        verdicts.append(
            ConstraintViolation(
                constraint_id=constraint.constraint_id,
                severity=constraint.severity,
                slot_id=constraint.slot_id,
                operator=constraint.operator,
                expected=str(expected),
                actual=str(actual),
                violated=violated,
                penalty=penalty,
                events=events,
            )
        )

    return ConstraintReport(
        ok=not hard_fail,
        hard_fail=hard_fail,
        constraint_mode="hard_soft_v1",
        total_constraints=total_constraints,
        violations=verdicts,
        penalty_total=penalty_total if penalty_seen else None,
        notes=[],
    )


def check_composite_constraints(
    *,
    constraints: Iterable[CompositeConstraint],
    slot_registry: SlotRegistry,
    state: Any,
) -> list[ConstraintViolation]:
    """Evaluate composite constraints that reference multiple slots via expressions."""
    verdicts: list[ConstraintViolation] = []

    for constraint in constraints:
        slot_values: dict[str, Decimal] = {}
        for slot_id in constraint.slot_refs:
            slot_spec = slot_registry.slots.get(slot_id)
            if slot_spec is None or not slot_spec.state_path:
                raise ValueError(
                    f"CompositeConstraint '{constraint.constraint_id}' references unknown slot '{slot_id}'"
                )
            sv = get_state_path(state, slot_spec.state_path)
            if np.ndim(sv) != 0:
                raise ValueError(
                    f"CompositeConstraint '{constraint.constraint_id}' slot '{slot_id}' must be scalar"
                )
            slot_values[slot_id] = decimal_from_numeric(
                sv,
                label=f"composite constraint '{constraint.constraint_id}' slot '{slot_id}'",
            )

        actual = _safe_eval_expression(constraint.expression, slot_values)
        expected = _coerce_number(constraint.expected)
        if expected is None:
            raise ValueError(
                f"CompositeConstraint '{constraint.constraint_id}' has non-numeric expected value"
            )

        violated = _is_violated(constraint.operator, current=actual, expected=expected)

        verdicts.append(
            ConstraintViolation(
                constraint_id=constraint.constraint_id,
                severity=constraint.severity,
                slot_id=",".join(constraint.slot_refs),
                operator=constraint.operator,
                expected=str(expected),
                actual=str(actual),
                violated=violated,
                penalty=constraint.penalty if violated else None,
                events=[
                    {
                        "event": "composite_constraint_evaluated",
                        "constraint_id": constraint.constraint_id,
                        "expression": constraint.expression,
                        "slot_values": {k: str(v) for k, v in slot_values.items()},
                        "ok": not violated,
                    }
                ],
            )
        )

    return verdicts


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_violated(operator: str, *, current: Decimal, expected: Decimal) -> bool:
    if operator == ">=":
        return current < expected
    if operator == ">":
        return current <= expected
    if operator == "<=":
        return current > expected
    if operator == "<":
        return current >= expected
    if operator == "==":
        return current != expected
    if operator == "!=":
        return current == expected
    raise ValueError(f"Unsupported constraint operator '{operator}'")


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


def _aggregate(
    state_value: np.ndarray,
    aggregation: AggregationFunction,
    constraint: LoweredConstraint,
    expected: Decimal,
    *,
    slot_registry: SlotRegistry,
    state: Any,
) -> tuple[Decimal, list[dict[str, Any]], bool | None]:
    """Aggregate vector/tensor state to a scalar Decimal for comparison.

    Returns ``(aggregated_value, extra_events, violated_override)``.
    """
    events: list[dict[str, Any]] = []
    flat = require_finite_numpy(
        np.asarray(state_value).ravel(),
        label=f"constraint '{constraint.constraint_id}' state values",
    )
    violated_override: bool | None = None

    if aggregation == AggregationFunction.SCALAR:
        raise ValueError(
            f"Constraint '{constraint.constraint_id}' expects scalar slot value; "
            f"got ndim={np.ndim(state_value)}"
        )

    if aggregation == AggregationFunction.MIN:
        actual = decimal_from_numeric(np.min(flat), label=f"constraint '{constraint.constraint_id}' min")
    elif aggregation == AggregationFunction.MAX:
        actual = decimal_from_numeric(np.max(flat), label=f"constraint '{constraint.constraint_id}' max")
    elif aggregation == AggregationFunction.MEAN:
        actual = decimal_from_numeric(np.mean(flat), label=f"constraint '{constraint.constraint_id}' mean")
    elif aggregation == AggregationFunction.MEDIAN:
        actual = decimal_from_numeric(
            np.median(flat),
            label=f"constraint '{constraint.constraint_id}' median",
        )
    elif aggregation == AggregationFunction.SUM:
        actual = decimal_from_numeric(np.sum(flat), label=f"constraint '{constraint.constraint_id}' sum")
    elif aggregation == AggregationFunction.QUANTILE:
        q = validate_quantile(
            constraint.quantile_param,
            label=f"constraint '{constraint.constraint_id}' quantile_param",
        )
        actual = decimal_from_numeric(
            np.quantile(flat, q),
            label=f"constraint '{constraint.constraint_id}' quantile",
        )
    elif aggregation == AggregationFunction.WEIGHTED_MEAN:
        weights = _resolve_weights(
            constraint=constraint,
            slot_registry=slot_registry,
            state=state,
            expected_size=flat.size,
        )
        actual = decimal_from_numeric(
            np.average(flat, weights=weights),
            label=f"constraint '{constraint.constraint_id}' weighted mean",
        )
        events.append(
            {
                "event": "weighted_aggregation",
                "aggregation": aggregation.value,
                "weights_slot_id": constraint.weights_slot_id,
                "n_total": int(flat.size),
            }
        )
    elif aggregation == AggregationFunction.ALL:
        element_violations = _check_elementwise(flat, constraint.operator, expected)
        n_violating = sum(element_violations)
        actual = Decimal("1") if n_violating == 0 else Decimal("0")
        violated_override = n_violating > 0
        events.append(_build_elementwise_event(element_violations))
    elif aggregation == AggregationFunction.ANY:
        element_violations = _check_elementwise(flat, constraint.operator, expected)
        n_satisfying = sum(1 for v in element_violations if not v)
        actual = Decimal("1") if n_satisfying > 0 else Decimal("0")
        violated_override = n_satisfying == 0
        events.append(_build_elementwise_event(element_violations))
    elif aggregation == AggregationFunction.COUNT_VIOLATING:
        element_violations = _check_elementwise(flat, constraint.operator, expected)
        n_violating = sum(element_violations)
        actual = Decimal(n_violating)
        events.append(_build_elementwise_event(element_violations))
    else:
        raise ValueError(f"Unsupported aggregation: {aggregation}")

    return actual, events, violated_override


def _resolve_weights(
    *,
    constraint: LoweredConstraint,
    slot_registry: SlotRegistry,
    state: Any,
    expected_size: int,
) -> np.ndarray:
    if not constraint.weights_slot_id:
        raise ValueError(
            f"Constraint '{constraint.constraint_id}' with weighted_mean aggregation "
            "requires weights_slot_id"
        )
    weight_slot = slot_registry.slots.get(constraint.weights_slot_id)
    if weight_slot is None or not weight_slot.state_path:
        raise ValueError(
            f"Constraint '{constraint.constraint_id}' references unknown weights slot "
            f"'{constraint.weights_slot_id}'"
        )
    weights = np.asarray(get_state_path(state, weight_slot.state_path), dtype=float).ravel()
    weights = require_finite_numpy(
        weights,
        label=f"constraint '{constraint.constraint_id}' weights",
    )
    if weights.size != expected_size:
        raise ValueError(
            f"Constraint '{constraint.constraint_id}' weights shape mismatch: "
            f"expected {expected_size}, got {weights.size}"
        )
    if np.any(weights < 0):
        raise ValueError(
            f"Constraint '{constraint.constraint_id}' weights must be non-negative"
        )
    total = float(np.sum(weights))
    if total <= 0.0:
        raise ValueError(
            f"Constraint '{constraint.constraint_id}' weights must sum to a positive value"
        )
    return weights / total


def _build_elementwise_event(element_violations: list[bool]) -> dict[str, Any]:
    violating_indices = [i for i, violated in enumerate(element_violations) if violated][:100]
    n_total = len(element_violations)
    n_violating = sum(element_violations)
    return {
        "event": "elementwise_check",
        "n_total": n_total,
        "n_satisfying": n_total - n_violating,
        "n_violating": n_violating,
        "violating_indices": violating_indices,
    }


def _check_elementwise(
    values: np.ndarray,
    operator: str,
    expected: Decimal,
) -> list[bool]:
    """Return per-element violation flags (True = violated)."""
    return [
        _is_violated(
            operator,
            current=decimal_from_numeric(v.item(), label="constraint element"),
            expected=expected,
        )
        for v in np.nditer(values)
    ]


# ---------------------------------------------------------------------------
# Safe expression evaluator for CompositeConstraint
# ---------------------------------------------------------------------------

_ALLOWED_BINOPS = {
    ast.Add: op_module.add,
    ast.Sub: op_module.sub,
    ast.Mult: op_module.mul,
    ast.Div: op_module.truediv,
    ast.Pow: op_module.pow,
}

_ALLOWED_UNARYOPS = {
    ast.USub: op_module.neg,
}


def _safe_eval_expression(expression: str, slot_values: dict[str, Decimal]) -> Decimal:
    """Evaluate a simple arithmetic expression over slot values.

    Only allows: numeric constants, slot name references, and basic arithmetic
    (+, -, *, /, **). No function calls, attribute access, or other constructs.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid constraint expression: {expression!r}") from exc

    def _eval_node(node: ast.expr) -> Decimal:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return decimal_from_numeric(node.value, label="constraint constant")
        if isinstance(node, ast.Name):
            if node.id not in slot_values:
                raise ValueError(
                    f"Unknown slot reference '{node.id}' in expression '{expression}'"
                )
            return slot_values[node.id]
        if isinstance(node, ast.BinOp):
            op_func = _ALLOWED_BINOPS.get(type(node.op))
            if op_func is None:
                raise ValueError(
                    f"Unsupported operator {type(node.op).__name__} in expression '{expression}'"
                )
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ValueError(f"Division by zero in expression '{expression}'")
                return left / right
            return decimal_from_numeric(
                op_func(float(left), float(right)),
                label=f"expression '{expression}'",
            )
        if isinstance(node, ast.UnaryOp):
            op_func = _ALLOWED_UNARYOPS.get(type(node.op))
            if op_func is None:
                raise ValueError(
                    f"Unsupported unary operator {type(node.op).__name__} in expression '{expression}'"
                )
            return decimal_from_numeric(
                op_func(float(_eval_node(node.operand))),
                label=f"expression '{expression}'",
            )
        raise ValueError(
            f"Disallowed AST node {type(node).__name__} in expression '{expression}'"
        )

    return _eval_node(tree)
