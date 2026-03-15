from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

import numpy as np

from polisyos.core.contracts.foundry import ConstraintReport, ConstraintViolation, LoweredConstraint
from polisyos.ir.kernel import SlotRegistry
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue

from ._executor_models import get_state_path


def check_constraints(
    *,
    constraints: Iterable[LoweredConstraint],
    slot_registry: SlotRegistry,
    state: Any,
) -> ConstraintReport:
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
        if np.ndim(state_value) != 0:
            raise ValueError(f"Constraint '{constraint.constraint_id}' expects scalar slot value")
        actual = Decimal(str(float(state_value)))
        violated = _is_violated(constraint.operator, current=actual, expected=expected)

        penalty = None
        if violated and constraint.severity == "soft" and constraint.penalty is not None:
            penalty = constraint.penalty
            penalty_total += penalty
            penalty_seen = True
        if violated and constraint.severity == "hard":
            hard_fail = True

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
                events=[
                    {
                        "event": "constraint_evaluated",
                        "constraint_id": constraint.constraint_id,
                        "slot_id": constraint.slot_id,
                        "ok": not violated,
                    }
                ],
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
