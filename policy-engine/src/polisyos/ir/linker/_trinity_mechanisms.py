"""Mechanism, selector, constraint, and schedule validation for Trinity linker."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Iterable

from polisyos.ir.kernel.merge_rules import MergeRuleKind, MergeRuleRegistry
from polisyos.ir.kernel.selector_fields import SelectorFieldRegistry
from polisyos.ir.kernel.slots import SlotRegistry, SlotValueType
from polisyos.ir.kernel.units import MoneyUnit, RateUnit, UnitsRegistry
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.ir.governance.policy_spec import InterventionSpec
from polisyos.ir.governance.problem_frame import ConstraintSpec
from polisyos.ir.governance.schedule import ScheduleSpec, schedule_range
from polisyos.ir.governance.selector_expr import (
    SelectorAll,
    SelectorAny,
    SelectorExpr,
    SelectorNot,
    SelectorPredicate,
)

from .reports import LinkIssue, LinkIssueCode, LinkSeverity


def _validate_mechanism_slots(
    slot_registry: SlotRegistry,
    issues: list[LinkIssue],
    *,
    ids: dict[str, str],
    path_prefix: list[str | int],
    reads_slots: Iterable[str],
    writes_slots: Iterable[str],
) -> None:
    for slot_id in list(reads_slots):
        if slot_id not in slot_registry.slots:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.MISSING_SLOT,
                    message=f"Missing slot '{slot_id}' referenced by mechanism",
                    path=path_prefix,
                    ids=ids,
                    data={"slot_id": slot_id, "where": "mechanism_reads"},
                )
            )
    for slot_id in list(writes_slots):
        if slot_id not in slot_registry.slots:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.MISSING_SLOT,
                    message=f"Missing slot '{slot_id}' referenced by mechanism",
                    path=path_prefix,
                    ids=ids,
                    data={"slot_id": slot_id, "where": "mechanism_writes"},
                )
            )


def _validate_selector_fields(
    target: SelectorExpr,
    registry: SelectorFieldRegistry,
    issues: list[LinkIssue],
    *,
    ids: dict[str, str],
    path_prefix: list[str | int],
) -> None:
    fields = _collect_selector_fields(target)
    scopes = set()
    for field_id in sorted(fields):
        spec = registry.fields.get(field_id)
        if spec is None:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.UNKNOWN_SELECTOR_FIELD,
                    message=f"Unknown selector field '{field_id}'",
                    path=path_prefix + ["field"],
                    ids=ids,
                    data={"field_id": field_id},
                )
            )
            continue
        scopes.add(spec.scope)
    if len(scopes) > 1:
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.SELECTOR_SCOPE_MISMATCH,
                message="Selector fields must target a single scope",
                path=path_prefix,
                ids=ids,
                data={"scopes": sorted([scope.value for scope in scopes])},
            )
        )


def _collect_selector_fields(node: SelectorExpr) -> set[str]:
    if isinstance(node, SelectorPredicate):
        return {node.field}
    if isinstance(node, SelectorNot):
        return _collect_selector_fields(node.clause)
    if isinstance(node, (SelectorAll, SelectorAny)):
        fields: set[str] = set()
        for clause in node.clauses:
            fields.update(_collect_selector_fields(clause))
        return fields
    return set()


def _validate_constraint_slot(
    slot_id: str,
    slot_registry: SlotRegistry | None,
    issues: list[LinkIssue],
    *,
    ids: dict[str, str],
    path: list[str | int],
) -> None:
    if slot_registry is None:
        return
    if slot_id not in slot_registry.slots:
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.MISSING_SLOT,
                message=f"Missing slot '{slot_id}' referenced by constraint",
                path=path,
                ids=ids,
                data={"slot_id": slot_id, "where": "constraint"},
            )
        )


def _validate_constraint_unit(
    constraint: ConstraintSpec,
    unit_id: str,
    units_registry: UnitsRegistry | None,
    issues: list[LinkIssue],
    *,
    ids: dict[str, str],
    path: list[str | int],
    strict: bool,
    missing_registry_emitted: set[str],
) -> None:
    if units_registry is None:
        if strict and "units" not in missing_registry_emitted:
            missing_registry_emitted.add("units")
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.MISSING_REGISTRY,
                    message="Missing required registry 'units'",
                    path=path,
                    data={"registry": "units"},
                )
            )
        return
    unit = units_registry.units.get(unit_id)
    if unit is None:
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.UNKNOWN_UNIT,
                message=f"Unknown unit '{unit_id}' for constraint",
                path=path,
                ids=ids,
                data={"unit_id": unit_id, "where": "constraint"},
            )
        )
        return

    if isinstance(unit, MoneyUnit):
        if isinstance(constraint.value, MoneyValue):
            if constraint.value.currency != unit.currency:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.INCOMPATIBLE_CONSTRAINT,
                        message=(
                            f"Constraint '{constraint.constraint_id}' currency "
                            f"'{constraint.value.currency}' does not match '{unit.currency}'"
                        ),
                        path=path,
                        ids=ids,
                        data={"expected": unit.currency, "actual": constraint.value.currency},
                    )
                )
        elif not _is_scalar_numeric_constraint_value(constraint.value):
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.INCOMPATIBLE_CONSTRAINT,
                    message=(
                        f"Constraint '{constraint.constraint_id}' requires MoneyValue with currency"
                    ),
                    path=path,
                    ids=ids,
                )
            )
        return

    if isinstance(unit, RateUnit):
        if isinstance(constraint.value, RateValue):
            if constraint.value.base != unit.base:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.INCOMPATIBLE_CONSTRAINT,
                        message=(
                            f"Constraint '{constraint.constraint_id}' rate base '{constraint.value.base}' "
                            f"does not match '{unit.base}'"
                        ),
                        path=path,
                        ids=ids,
                        data={"expected": unit.base, "actual": constraint.value.base},
                    )
                )
            return

        if not _is_scalar_numeric_constraint_value(constraint.value):
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.INCOMPATIBLE_CONSTRAINT,
                    message=(
                        f"Constraint '{constraint.constraint_id}' requires RateValue or numeric scalar"
                    ),
                    path=path,
                    ids=ids,
                )
            )


def _is_scalar_numeric_constraint_value(value: object) -> bool:
    if isinstance(value, (MoneyValue, RateValue, CountValue, DurationValue)):
        return True
    if isinstance(value, Decimal):
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        try:
            Decimal(value)
            return True
        except InvalidOperation:
            return False
    return False


def _schedule_overlaps(left: ScheduleSpec, right: ScheduleSpec) -> bool:
    left_start, left_end = schedule_range(left)
    right_start, right_end = schedule_range(right)
    return not (left_end < right_start or right_end < left_start)


def _validate_schedule_conflicts(
    interventions: list[InterventionSpec],
    intervention_writes: dict[str, tuple[list[str], ScheduleSpec, int | None]],
    *,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    issues: list[LinkIssue],
) -> None:
    writers: dict[str, list[InterventionSpec]] = {}
    for intervention in interventions:
        entry = intervention_writes.get(intervention.intervention_id)
        if entry is None:
            continue
        writes, _, _ = entry
        for slot_id in writes:
            writers.setdefault(slot_id, []).append(intervention)

    for slot_id, interventions_for_slot in writers.items():
        if len(interventions_for_slot) < 2:
            continue
        slot = slot_registry.slots.get(slot_id)
        if slot is None:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.MISSING_SLOT,
                    message=f"Missing slot '{slot_id}' for merge evaluation",
                    path=["policy_spec", "interventions"],
                    data={"slot_id": slot_id},
                )
            )
            continue
        rule = merge_registry.rules.get(slot.merge_rule.rule_id)
        if rule is None:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.UNKNOWN_MERGE_RULE,
                    message=(
                        f"Unknown merge rule '{slot.merge_rule.rule_id}' for '{slot_id}'"
                    ),
                    path=["policy_spec", "interventions"],
                    data={"slot_id": slot_id},
                )
            )
            continue

        overlapping: set[str] = set()
        for idx, left in enumerate(interventions_for_slot):
            for right in interventions_for_slot[idx + 1 :]:
                if _schedule_overlaps(left.schedule, right.schedule):
                    overlapping.add(left.intervention_id)
                    overlapping.add(right.intervention_id)

        if not overlapping:
            continue

        if rule.allowed_value_types is not None:
            if slot.value_type.value not in rule.allowed_value_types:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.MERGE_RULE_CONFLICT,
                        message=(
                            f"Merge rule '{rule.rule_id}' incompatible with slot type "
                            f"'{slot.value_type.value}'"
                        ),
                        path=["policy_spec", "interventions"],
                        data={"slot_id": slot_id, "rule_id": rule.rule_id},
                    )
                )
                continue
        elif rule.kind == MergeRuleKind.SUM and slot.value_type not in {
            SlotValueType.INT,
            SlotValueType.DECIMAL,
        }:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.MERGE_RULE_CONFLICT,
                    message=(
                        f"Merge rule '{rule.rule_id}' incompatible with slot type "
                        f"'{slot.value_type.value}'"
                    ),
                    path=["policy_spec", "interventions"],
                    data={"slot_id": slot_id, "rule_id": rule.rule_id},
                )
            )
            continue

        if rule.kind == MergeRuleKind.ERROR:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.MERGE_RULE_CONFLICT,
                    message=f"Merge conflict for slot '{slot_id}'",
                    path=["policy_spec", "interventions"],
                    data={"slot_id": slot_id, "intervention_ids": sorted(overlapping)},
                )
            )
        elif rule.kind == MergeRuleKind.PRIORITY:
            if rule.default_priority is None:
                missing = [
                    intervention.intervention_id
                    for intervention in interventions_for_slot
                    if intervention.intervention_id in overlapping
                    and intervention.priority is None
                ]
                if missing:
                    issues.append(
                        LinkIssue(
                            severity=LinkSeverity.ERROR,
                            code=LinkIssueCode.MERGE_RULE_CONFLICT,
                            message=(
                                f"Merge rule 'priority' requires priority for slot '{slot_id}'"
                            ),
                            path=["policy_spec", "interventions"],
                            data={"slot_id": slot_id, "missing": sorted(missing)},
                        )
                    )


__all__ = [
    "_collect_selector_fields",
    "_schedule_overlaps",
    "_validate_constraint_slot",
    "_validate_constraint_unit",
    "_validate_mechanism_slots",
    "_validate_schedule_conflicts",
    "_validate_selector_fields",
]
