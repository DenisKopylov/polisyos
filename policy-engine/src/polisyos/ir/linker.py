from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import Field

from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.kernel.constraints import ConstraintRegistry
from polisyos.ir.kernel.mechanisms import MechanismTypeRegistry, ParamType
from polisyos.ir.kernel.merge_rules import MergeRuleKind, MergeRuleRegistry
from polisyos.ir.kernel.metrics import MetricRegistry
from polisyos.ir.kernel.selector_fields import SelectorFieldRegistry
from polisyos.ir.kernel.slots import SlotRegistry
from polisyos.ir.kernel.units import (
    CountUnit,
    DurationUnit,
    MoneyUnit,
    RateUnit,
    UnitsRegistry,
)
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.ir.surface import (
    InterventionSpec,
    PolicySurfaceIR,
    SelectorAll,
    SelectorAny,
    SelectorExpr,
    SelectorNot,
    SelectorPredicate,
    ScheduleSpec,
    schedule_range,
)


class LinkIssue(KernelModel):
    severity: Literal["error", "warning"] = "error"
    code: str
    message: str
    path: list[str | int] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class LinkReport(KernelModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    ok: bool
    issues: list[LinkIssue] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def link_policy(
    policy: PolicySurfaceIR,
    mechanism_registry: MechanismTypeRegistry,
    *,
    slot_registry: SlotRegistry | None = None,
    merge_registry: MergeRuleRegistry | None = None,
    constraint_registry: ConstraintRegistry | None = None,
    metric_registry: MetricRegistry | None = None,
    selector_field_registry: SelectorFieldRegistry | None = None,
    units_registry: UnitsRegistry | None = None,
    allow_extra_params: bool = False,
) -> LinkReport:
    issues: list[LinkIssue] = []

    for idx, intervention in enumerate(policy.semantic.interventions):
        mech = mechanism_registry.mechanisms.get(intervention.kind)
        if mech is None:
            issues.append(
                LinkIssue(
                    code="unknown_mechanism",
                    message=f"Unknown mechanism '{intervention.kind}'",
                    path=["semantic", "interventions", idx, "kind"],
                )
            )
            continue

        _validate_params(
            intervention,
            mech,
            issues,
            path_prefix=["semantic", "interventions", idx, "params"],
            allow_extra_params=allow_extra_params,
            units_registry=units_registry,
        )
        if slot_registry is not None:
            _validate_mechanism_slots(
                mech,
                slot_registry,
                issues,
                path_prefix=["semantic", "interventions", idx, "kind"],
            )
        if selector_field_registry is not None:
            _validate_selector_fields(
                intervention.target,
                selector_field_registry,
                issues,
                path_prefix=["semantic", "interventions", idx, "target"],
            )

    if constraint_registry is not None:
        _validate_constraints(policy, constraint_registry, issues)

    if metric_registry is not None:
        _validate_objectives(policy, metric_registry, issues)

    if units_registry is not None:
        if slot_registry is not None:
            _validate_slot_units(slot_registry, units_registry, issues)
        if constraint_registry is not None:
            _validate_constraint_units(
                policy,
                constraint_registry,
                units_registry,
                slot_registry=slot_registry,
                issues=issues,
            )
        if metric_registry is not None:
            _validate_metric_units(policy, metric_registry, units_registry, issues)

    if slot_registry is not None and merge_registry is not None:
        _validate_schedule_conflicts(
            policy.semantic.interventions,
            mechanism_registry=mechanism_registry,
            slot_registry=slot_registry,
            merge_registry=merge_registry,
            issues=issues,
        )

    ok = not any(issue.severity == "error" for issue in issues)
    return LinkReport(ok=ok, issues=issues)


def _validate_params(
    intervention: InterventionSpec,
    mech,
    issues: list[LinkIssue],
    *,
    path_prefix: list[str | int],
    allow_extra_params: bool,
    units_registry: UnitsRegistry | None,
) -> None:
    params = intervention.params
    spec_params = mech.params

    for param_id, spec in spec_params.items():
        value = _get_param_value(params, param_id)
        if value is None:
            if spec.required:
                issues.append(
                    LinkIssue(
                        code="missing_param",
                        message=f"Missing required param '{param_id}' for '{mech.mechanism_id}'",
                        path=path_prefix + [param_id],
                    )
                )
            continue
        _validate_param_value(value, spec, issues, path_prefix + [param_id])
        _validate_param_unit(value, spec, issues, path_prefix + [param_id], units_registry)

    if not allow_extra_params:
        for key in params.keys():
            if key not in spec_params:
                issues.append(
                    LinkIssue(
                        code="unknown_param",
                        message=f"Unknown param '{key}' for '{mech.mechanism_id}'",
                        path=path_prefix + [key],
                    )
                )


def _get_param_value(params: dict[str, Any], path: str) -> Any:
    current: Any = params
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, RateValue):
        return value.as_ratio()
    if isinstance(value, MoneyValue):
        return value.amount
    if isinstance(value, CountValue):
        return Decimal(value.value)
    if isinstance(value, DurationValue):
        return Decimal(value.value)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return None
    return None


def _as_rate_decimal(value: Any) -> Decimal | None:
    if isinstance(value, RateValue):
        return value.as_ratio()
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            text = text[:-1].strip()
            try:
                return Decimal(text) / Decimal("100")
            except InvalidOperation:
                return None
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    return None


def _validate_param_value(
    value: Any,
    spec,
    issues: list[LinkIssue],
    path: list[str | int],
) -> None:
    if spec.value_type == ParamType.BOOL and not isinstance(value, bool):
        issues.append(
            LinkIssue(
                code="param_type",
                message=f"Param '{spec.param_id}' expects bool",
                path=path,
            )
        )
        return
    if spec.value_type == ParamType.STRING and not isinstance(value, str):
        issues.append(
            LinkIssue(
                code="param_type",
                message=f"Param '{spec.param_id}' expects string",
                path=path,
            )
        )
        return
    if spec.value_type == ParamType.OBJECT and not isinstance(value, dict):
        issues.append(
            LinkIssue(
                code="param_type",
                message=f"Param '{spec.param_id}' expects object",
                path=path,
            )
        )
        return
    if spec.value_type == ParamType.ARRAY and not isinstance(value, list):
        issues.append(
            LinkIssue(
                code="param_type",
                message=f"Param '{spec.param_id}' expects array",
                path=path,
            )
        )
        return

    if spec.enum_values is not None:
        if value not in spec.enum_values:
            issues.append(
                LinkIssue(
                    code="param_enum",
                    message=f"Param '{spec.param_id}' must be one of {spec.enum_values}",
                    path=path,
                )
            )
            return

    if spec.value_type == ParamType.RATE:
        numeric = _as_rate_decimal(value)
        if numeric is None:
            issues.append(
                LinkIssue(
                    code="param_type",
                    message=f"Param '{spec.param_id}' expects rate value",
                    path=path,
                )
            )
            return
    else:
        numeric = _as_decimal(value)
        if numeric is None:
            if spec.value_type in {
                ParamType.DECIMAL,
                ParamType.INT,
                ParamType.MONEY,
                ParamType.COUNT,
                ParamType.DURATION,
            }:
                issues.append(
                    LinkIssue(
                        code="param_type",
                        message=f"Param '{spec.param_id}' expects numeric value",
                        path=path,
                    )
                )
            return

    if spec.value_type in {ParamType.INT, ParamType.COUNT, ParamType.DURATION}:
        if numeric != numeric.to_integral_value():
            issues.append(
                LinkIssue(
                    code="param_type",
                    message=f"Param '{spec.param_id}' expects integer value",
                    path=path,
                )
            )
            return

    if spec.min_value is not None and numeric < spec.min_value:
        issues.append(
            LinkIssue(
                code="param_range",
                message=f"Param '{spec.param_id}' below min {spec.min_value}",
                path=path,
            )
        )
    if spec.max_value is not None and numeric > spec.max_value:
        issues.append(
            LinkIssue(
                code="param_range",
                message=f"Param '{spec.param_id}' above max {spec.max_value}",
                path=path,
            )
        )


def _validate_param_unit(
    value: Any,
    spec,
    issues: list[LinkIssue],
    path: list[str | int],
    units_registry: UnitsRegistry | None,
) -> None:
    if units_registry is None or spec.unit_id is None:
        return
    unit = units_registry.units.get(spec.unit_id)
    if unit is None:
        issues.append(
            LinkIssue(
                code="unknown_unit",
                message=f"Unknown unit '{spec.unit_id}' for param '{spec.param_id}'",
                path=path + ["unit_id"],
            )
        )
        return
    if spec.value_type == ParamType.MONEY:
        if not isinstance(unit, MoneyUnit):
            issues.append(
                LinkIssue(
                    code="unit_mismatch",
                    message=f"Param '{spec.param_id}' expects money unit '{spec.unit_id}'",
                    path=path + ["unit_id"],
                )
            )
            return
        if isinstance(value, MoneyValue):
            if value.currency != unit.currency:
                issues.append(
                    LinkIssue(
                        code="money_currency_mismatch",
                        message=(
                            f"Param '{spec.param_id}' currency '{value.currency}' "
                            f"does not match unit '{unit.currency}'"
                        ),
                        path=path,
                    )
                )
        elif isinstance(value, (str, int, Decimal)) and spec.required:
            issues.append(
                LinkIssue(
                    code="money_currency_missing",
                    message=f"Param '{spec.param_id}' requires MoneyValue with currency",
                    path=path,
                )
            )
        return
    if spec.value_type == ParamType.RATE and not isinstance(unit, RateUnit):
        issues.append(
            LinkIssue(
                code="unit_mismatch",
                message=f"Param '{spec.param_id}' expects rate unit '{spec.unit_id}'",
                path=path + ["unit_id"],
            )
        )
        return
    if spec.value_type == ParamType.DURATION and not isinstance(unit, DurationUnit):
        issues.append(
            LinkIssue(
                code="unit_mismatch",
                message=f"Param '{spec.param_id}' expects duration unit '{spec.unit_id}'",
                path=path + ["unit_id"],
            )
        )
        return
    if spec.value_type == ParamType.COUNT and not isinstance(unit, CountUnit):
        issues.append(
            LinkIssue(
                code="unit_mismatch",
                message=f"Param '{spec.param_id}' expects count unit '{spec.unit_id}'",
                path=path + ["unit_id"],
            )
        )


def _validate_mechanism_slots(
    mech,
    slot_registry: SlotRegistry,
    issues: list[LinkIssue],
    *,
    path_prefix: list[str | int],
) -> None:
    for slot_id in list(mech.reads_slots) + list(mech.writes_slots):
        if slot_id not in slot_registry.slots:
            issues.append(
                LinkIssue(
                    code="unknown_slot",
                    message=f"Unknown slot '{slot_id}' referenced by '{mech.mechanism_id}'",
                    path=path_prefix,
                    data={"slot_id": slot_id},
                )
            )


def _validate_selector_fields(
    target: SelectorExpr,
    registry: SelectorFieldRegistry,
    issues: list[LinkIssue],
    *,
    path_prefix: list[str | int],
) -> None:
    fields = _collect_selector_fields(target)
    scopes = set()
    for field_id in sorted(fields):
        spec = registry.fields.get(field_id)
        if spec is None:
            issues.append(
                LinkIssue(
                    code="unknown_selector_field",
                    message=f"Unknown selector field '{field_id}'",
                    path=path_prefix + ["field"],
                    data={"field_id": field_id},
                )
            )
            continue
        scopes.add(spec.scope)
    if len(scopes) > 1:
        issues.append(
            LinkIssue(
                code="selector_scope_mismatch",
                message="Selector fields must target a single scope",
                path=path_prefix,
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


def _validate_constraints(
    policy: PolicySurfaceIR,
    constraint_registry: ConstraintRegistry,
    issues: list[LinkIssue],
) -> None:
    for idx, constraint in enumerate(policy.semantic.constraints):
        if constraint.constraint_id not in constraint_registry.constraints:
            issues.append(
                LinkIssue(
                    code="unknown_constraint",
                    message=f"Unknown constraint '{constraint.constraint_id}'",
                    path=["semantic", "constraints", idx, "constraint_id"],
                )
            )


def _validate_slot_units(
    slot_registry: SlotRegistry,
    units_registry: UnitsRegistry,
    issues: list[LinkIssue],
) -> None:
    for slot_id, slot in slot_registry.slots.items():
        if slot.unit is None:
            continue
        if slot.unit.unit_id not in units_registry.units:
            issues.append(
                LinkIssue(
                    code="unknown_unit",
                    message=f"Unknown unit '{slot.unit.unit_id}' for slot '{slot_id}'",
                    path=["registry", "slots", slot_id, "unit"],
                )
            )


def _validate_constraint_units(
    policy: PolicySurfaceIR,
    constraint_registry: ConstraintRegistry,
    units_registry: UnitsRegistry,
    *,
    slot_registry: SlotRegistry | None,
    issues: list[LinkIssue],
) -> None:
    for idx, constraint in enumerate(policy.semantic.constraints):
        spec = constraint_registry.constraints.get(constraint.constraint_id)
        if spec is None:
            continue
        if spec.unit_id is None:
            continue
        unit = units_registry.units.get(spec.unit_id)
        if unit is None:
            issues.append(
                LinkIssue(
                    code="unknown_unit",
                    message=f"Unknown unit '{spec.unit_id}' for constraint '{spec.constraint_id}'",
                    path=["semantic", "constraints", idx, "constraint_id"],
                )
            )
            continue
        if spec.slot_id and slot_registry is not None:
            if spec.slot_id not in slot_registry.slots:
                issues.append(
                    LinkIssue(
                        code="unknown_slot",
                        message=f"Unknown slot '{spec.slot_id}' for constraint '{spec.constraint_id}'",
                        path=["semantic", "constraints", idx, "constraint_id"],
                        data={"slot_id": spec.slot_id},
                    )
                )
        if isinstance(unit, MoneyUnit):
            if isinstance(constraint.value, MoneyValue):
                if constraint.value.currency != unit.currency:
                    issues.append(
                        LinkIssue(
                            code="money_currency_mismatch",
                            message=(
                                f"Constraint '{spec.constraint_id}' currency "
                                f"'{constraint.value.currency}' does not match '{unit.currency}'"
                            ),
                            path=["semantic", "constraints", idx, "value"],
                        )
                    )
            elif isinstance(constraint.value, (str, int, Decimal)):
                issues.append(
                    LinkIssue(
                        code="money_currency_missing",
                        message=f"Constraint '{spec.constraint_id}' requires MoneyValue with currency",
                        path=["semantic", "constraints", idx, "value"],
                    )
                )
def _validate_objectives(
    policy: PolicySurfaceIR,
    metric_registry: MetricRegistry,
    issues: list[LinkIssue],
) -> None:
    for idx, objective in enumerate(policy.semantic.objectives):
        if objective.metric_id not in metric_registry.metrics:
            issues.append(
                LinkIssue(
                    code="unknown_metric",
                    message=f"Unknown metric '{objective.metric_id}'",
                    path=["semantic", "objectives", idx, "metric_id"],
                )
                )


def _validate_metric_units(
    policy: PolicySurfaceIR,
    metric_registry: MetricRegistry,
    units_registry: UnitsRegistry,
    issues: list[LinkIssue],
) -> None:
    for idx, objective in enumerate(policy.semantic.objectives):
        spec = metric_registry.metrics.get(objective.metric_id)
        if spec is None or spec.unit_id is None:
            continue
        if spec.unit_id not in units_registry.units:
            issues.append(
                LinkIssue(
                    code="unknown_unit",
                    message=f"Unknown unit '{spec.unit_id}' for metric '{spec.metric_id}'",
                    path=["semantic", "objectives", idx, "metric_id"],
                )
            )
def _schedule_overlaps(left: ScheduleSpec, right: ScheduleSpec) -> bool:
    left_start, left_end = schedule_range(left)
    right_start, right_end = schedule_range(right)
    return not (left_end < right_start or right_end < left_start)


def _validate_schedule_conflicts(
    interventions: list[InterventionSpec],
    *,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    issues: list[LinkIssue],
) -> None:
    writers: dict[str, list[InterventionSpec]] = {}
    for intervention in interventions:
        mech = mechanism_registry.mechanisms.get(intervention.kind)
        if mech is None:
            continue
        for slot_id in mech.writes_slots:
            writers.setdefault(slot_id, []).append(intervention)

    for slot_id, interventions_for_slot in writers.items():
        if len(interventions_for_slot) < 2:
            continue
        slot = slot_registry.slots.get(slot_id)
        if slot is None:
            issues.append(
                LinkIssue(
                    code="unknown_slot",
                    message=f"Unknown slot '{slot_id}' for merge evaluation",
                    path=["semantic", "interventions"],
                    data={"slot_id": slot_id},
                )
            )
            continue
        rule = merge_registry.rules.get(slot.merge_rule.rule_id)
        if rule is None:
            issues.append(
                LinkIssue(
                    code="unknown_merge_rule",
                    message=f"Unknown merge rule '{slot.merge_rule.rule_id}' for '{slot_id}'",
                    path=["semantic", "interventions"],
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

        if rule.kind == MergeRuleKind.ERROR:
            issues.append(
                LinkIssue(
                    code="merge_conflict",
                    message=f"Merge conflict for slot '{slot_id}'",
                    path=["semantic", "interventions"],
                    data={"slot_id": slot_id, "intervention_ids": sorted(overlapping)},
                )
            )
        elif rule.kind == MergeRuleKind.PRIORITY:
            missing = [
                intervention.intervention_id
                for intervention in interventions_for_slot
                if intervention.intervention_id in overlapping and intervention.priority is None
            ]
            if missing:
                issues.append(
                    LinkIssue(
                        code="merge_priority_missing",
                        message=f"Merge rule 'priority' requires priority for slot '{slot_id}'",
                        path=["semantic", "interventions"],
                        data={"slot_id": slot_id, "missing": sorted(missing)},
                    )
                )
