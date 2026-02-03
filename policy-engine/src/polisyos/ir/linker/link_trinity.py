from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from pydantic import Field

from polisyos.ir.canon import CanonViolation, to_canonical_bytes
from polisyos.ir.kernel.base import ARTIFACT_ID_PATTERN, ID_PATTERN, KernelModel
from polisyos.ir.kernel.mechanisms import ParamType, resolve_mechanism_slots
from polisyos.ir.kernel.merge_rules import MergeRuleKind, MergeRuleRegistry
from polisyos.ir.kernel.selector_fields import SelectorFieldRegistry
from polisyos.ir.kernel.slots import SlotRegistry, SlotValueType
from polisyos.ir.kernel.units import (
    CountUnit,
    DurationUnit,
    MoneyUnit,
    RateUnit,
    UnitsRegistry,
)
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.ir.policy_spec import InterventionSpec
from polisyos.ir.problem_frame import ConstraintSpec
from polisyos.ir.registry_fragments import RegistryBundle
from polisyos.ir.schedule import ScheduleSpec, schedule_range
from polisyos.ir.selector_expr import (
    SelectorAll,
    SelectorAny,
    SelectorExpr,
    SelectorNot,
    SelectorPredicate,
)
from polisyos.ir.trinity import TrinityBundle

from .reports import LinkIssue, LinkIssueCode, LinkReport, LinkSeverity

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class LinkedIntervention(KernelModel):
    intervention_id: str = Field(..., pattern=ID_PATTERN)
    mechanism_id: str = Field(..., pattern=ID_PATTERN)
    reads_slots: list[str] = Field(default_factory=list)
    writes_slots: list[str] = Field(default_factory=list)
    schedule_start: int
    schedule_end: int


class TrinityBindings(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    interventions: list[LinkedIntervention] = Field(default_factory=list)
    used_mechanisms: list[str] = Field(default_factory=list)
    used_slots_read: list[str] = Field(default_factory=list)
    used_slots_write: list[str] = Field(default_factory=list)
    used_units: list[str] = Field(default_factory=list)
    used_metrics: list[str] = Field(default_factory=list)
    used_constraints: list[str] = Field(default_factory=list)
    used_selector_fields: list[str] = Field(default_factory=list)


class LinkedTrinityBundle(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    bundle: TrinityBundle
    registry_digest: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    bundle_digest: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    bindings: TrinityBindings = Field(default_factory=TrinityBindings)


def link_trinity(
    bundle: TrinityBundle,
    registries: RegistryBundle,
    *,
    allow_extra_params: bool = False,
    strict: bool = True,
) -> tuple[LinkedTrinityBundle, LinkReport]:
    issues: list[LinkIssue] = []
    notes: list[str] = []
    missing_registry_emitted: set[str] = set()

    used_mechanisms: set[str] = set()
    used_slots_read: set[str] = set()
    used_slots_write: set[str] = set()
    used_units: set[str] = set()
    used_metrics: set[str] = set()
    used_constraints: set[str] = set()
    used_selector_fields: set[str] = set()

    linked_interventions: list[LinkedIntervention] = []
    intervention_writes: dict[str, tuple[list[str], ScheduleSpec, int | None]] = {}

    def _emit_missing_registry(registry_name: str, path: list[str | int]) -> None:
        if not strict:
            return
        if registry_name in missing_registry_emitted:
            return
        missing_registry_emitted.add(registry_name)
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.MISSING_REGISTRY,
                message=f"Missing required registry '{registry_name}'",
                path=path,
                data={"registry": registry_name},
            )
        )

    # Step A: PolicySpec interventions vs mechanism registry
    if bundle.policy_spec.interventions and registries.mechanisms is None:
        _emit_missing_registry("mechanisms", ["policy_spec", "interventions"])
    if bundle.policy_spec.interventions and registries.slots is None:
        _emit_missing_registry("slots", ["policy_spec", "interventions"])
    if bundle.policy_spec.interventions and registries.selector_fields is None:
        _emit_missing_registry("selector_fields", ["policy_spec", "interventions"])

    mechanisms = registries.mechanisms
    slots = registries.slots
    selector_fields = registries.selector_fields
    units = registries.units

    for idx, intervention in enumerate(bundle.policy_spec.interventions):
        ids = {"intervention_id": intervention.intervention_id}
        mech = mechanisms.mechanisms.get(intervention.kind) if mechanisms is not None else None
        if mech is None:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.UNKNOWN_MECHANISM,
                    message=f"Unknown mechanism '{intervention.kind}'",
                    path=["policy_spec", "interventions", idx, "kind"],
                    ids=ids,
                )
            )
            continue

        used_mechanisms.add(intervention.kind)

        _validate_params(
            intervention,
            mech,
            issues,
            path_prefix=["policy_spec", "interventions", idx, "params"],
            ids=ids,
            allow_extra_params=allow_extra_params,
            units_registry=units,
            used_units=used_units,
            missing_registry_emitted=missing_registry_emitted,
            strict=strict,
        )

        reads_slots, writes_slots = resolve_mechanism_slots(mech, intervention.params)
        used_slots_read.update(reads_slots)
        used_slots_write.update(writes_slots)

        if slots is None:
            if (reads_slots or writes_slots) and strict:
                _emit_missing_registry("slots", ["policy_spec", "interventions", idx])
        else:
            _validate_mechanism_slots(
                slots,
                issues,
                ids=ids,
                path_prefix=["policy_spec", "interventions", idx, "kind"],
                reads_slots=reads_slots,
                writes_slots=writes_slots,
            )

        fields = _collect_selector_fields(intervention.target)
        used_selector_fields.update(fields)
        if selector_fields is None:
            if fields and strict:
                _emit_missing_registry("selector_fields", ["policy_spec", "interventions", idx])
        else:
            _validate_selector_fields(
                intervention.target,
                selector_fields,
                issues,
                ids=ids,
                path_prefix=["policy_spec", "interventions", idx, "target"],
            )

        schedule_start, schedule_end = schedule_range(intervention.schedule)
        linked_interventions.append(
            LinkedIntervention(
                intervention_id=intervention.intervention_id,
                mechanism_id=intervention.kind,
                reads_slots=list(reads_slots),
                writes_slots=list(writes_slots),
                schedule_start=schedule_start,
                schedule_end=schedule_end,
            )
        )
        intervention_writes[intervention.intervention_id] = (
            list(writes_slots),
            intervention.schedule,
            intervention.priority,
        )

    # Step B: ProblemFrame objectives/KPIs vs metrics/units registries
    metrics = registries.metrics
    if (bundle.problem_frame.objectives or bundle.problem_frame.kpis) and metrics is None:
        _emit_missing_registry("metrics", ["problem_frame"])

    for idx, objective in enumerate(bundle.problem_frame.objectives):
        used_metrics.add(objective.metric_id)
        if metrics is None:
            continue
        metric_spec = metrics.metrics.get(objective.metric_id)
        if metric_spec is None:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.UNKNOWN_METRIC,
                    message=f"Unknown metric '{objective.metric_id}'",
                    path=["problem_frame", "objectives", idx, "metric_id"],
                    ids={"objective_id": objective.objective_id},
                    data={"metric_id": objective.metric_id},
                )
            )
            continue
        if metric_spec.unit_id is not None:
            used_units.add(metric_spec.unit_id)
            if units is None:
                _emit_missing_registry("units", ["problem_frame", "objectives", idx])
            elif metric_spec.unit_id not in units.units:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.UNKNOWN_UNIT,
                        message=f"Unknown unit '{metric_spec.unit_id}' for metric",
                        path=["problem_frame", "objectives", idx, "metric_id"],
                        ids={"objective_id": objective.objective_id},
                        data={"unit_id": metric_spec.unit_id},
                    )
                )

    for idx, kpi in enumerate(bundle.problem_frame.kpis):
        used_metrics.add(kpi.metric_id)
        if metrics is not None:
            metric_spec = metrics.metrics.get(kpi.metric_id)
            if metric_spec is None:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.UNKNOWN_METRIC,
                        message=f"Unknown metric '{kpi.metric_id}'",
                        path=["problem_frame", "kpis", idx, "metric_id"],
                        ids={"kpi_id": kpi.kpi_id},
                        data={"metric_id": kpi.metric_id},
                    )
                )
            elif metric_spec.unit_id is not None:
                used_units.add(metric_spec.unit_id)
                if units is None:
                    _emit_missing_registry("units", ["problem_frame", "kpis", idx])
                elif metric_spec.unit_id not in units.units:
                    issues.append(
                        LinkIssue(
                            severity=LinkSeverity.ERROR,
                            code=LinkIssueCode.UNKNOWN_UNIT,
                            message=f"Unknown unit '{metric_spec.unit_id}' for metric",
                            path=["problem_frame", "kpis", idx, "metric_id"],
                            ids={"kpi_id": kpi.kpi_id},
                            data={"unit_id": metric_spec.unit_id},
                        )
                    )
        if kpi.unit_id is not None:
            used_units.add(kpi.unit_id)
            if units is None:
                _emit_missing_registry("units", ["problem_frame", "kpis", idx])
            elif kpi.unit_id not in units.units:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.UNKNOWN_UNIT,
                        message=f"Unknown unit '{kpi.unit_id}' for KPI",
                        path=["problem_frame", "kpis", idx, "unit_id"],
                        ids={"kpi_id": kpi.kpi_id},
                        data={"unit_id": kpi.unit_id},
                    )
                )

    # Step C: ProblemFrame constraints vs constraint/slot/unit registries
    constraints = registries.constraints
    if (bundle.problem_frame.hard_constraints or bundle.problem_frame.soft_constraints) and constraints is None:
        _emit_missing_registry("constraints", ["problem_frame"])

    for list_name, constraints_list in (
        ("hard_constraints", bundle.problem_frame.hard_constraints),
        ("soft_constraints", bundle.problem_frame.soft_constraints),
    ):
        for idx, constraint in enumerate(constraints_list):
            used_constraints.add(constraint.constraint_id)
            ids = {"constraint_id": constraint.constraint_id}
            if constraints is not None:
                spec = constraints.constraints.get(constraint.constraint_id)
                if spec is None:
                    issues.append(
                        LinkIssue(
                            severity=LinkSeverity.ERROR,
                            code=LinkIssueCode.UNKNOWN_CONSTRAINT,
                            message=f"Unknown constraint '{constraint.constraint_id}'",
                            path=["problem_frame", list_name, idx, "constraint_id"],
                            ids=ids,
                            data={"constraint_id": constraint.constraint_id},
                        )
                    )
                else:
                    if spec.slot_id is not None:
                        _validate_constraint_slot(
                            spec.slot_id,
                            slots,
                            issues,
                            ids=ids,
                            path=["problem_frame", list_name, idx, "constraint_id"],
                        )
                    if spec.unit_id is not None:
                        used_units.add(spec.unit_id)
                        _validate_constraint_unit(
                            constraint,
                            spec.unit_id,
                            units,
                            issues,
                            ids=ids,
                            path=["problem_frame", list_name, idx, "value"],
                            strict=strict,
                            missing_registry_emitted=missing_registry_emitted,
                        )

            if constraint.slot_id is not None:
                _validate_constraint_slot(
                    constraint.slot_id,
                    slots,
                    issues,
                    ids=ids,
                    path=["problem_frame", list_name, idx, "slot_id"],
                )
                if slots is not None:
                    slot_spec = slots.slots.get(constraint.slot_id)
                    if slot_spec is not None and slot_spec.unit is not None:
                        used_units.add(slot_spec.unit.unit_id)
                        _validate_constraint_unit(
                            constraint,
                            slot_spec.unit.unit_id,
                            units,
                            issues,
                            ids=ids,
                            path=["problem_frame", list_name, idx, "value"],
                            strict=strict,
                            missing_registry_emitted=missing_registry_emitted,
                        )

    # Step D: Merge/schedule conflict checks
    if bundle.policy_spec.interventions and registries.merge_rules is None:
        _emit_missing_registry("merge_rules", ["policy_spec", "interventions"])

    if slots is not None and registries.merge_rules is not None:
        _validate_schedule_conflicts(
            bundle.policy_spec.interventions,
            intervention_writes,
            slot_registry=slots,
            merge_registry=registries.merge_rules,
            issues=issues,
        )

    bindings = TrinityBindings(
        interventions=linked_interventions,
        used_mechanisms=sorted(used_mechanisms),
        used_slots_read=sorted(used_slots_read),
        used_slots_write=sorted(used_slots_write),
        used_units=sorted(used_units),
        used_metrics=sorted(used_metrics),
        used_constraints=sorted(used_constraints),
        used_selector_fields=sorted(used_selector_fields),
    )

    registry_digest = _digest(registries, "registry", notes)
    bundle_digest = _digest(bundle, "bundle", notes)

    ok = not any(issue.severity == LinkSeverity.ERROR for issue in issues)
    report = LinkReport(ok=ok, issues=issues, notes=notes)
    linked = LinkedTrinityBundle(
        bundle=bundle,
        registry_digest=registry_digest,
        bundle_digest=bundle_digest,
        bindings=bindings,
    )
    return linked, report


def _digest(obj: Any, label: str, notes: list[str]) -> str | None:
    try:
        payload = to_canonical_bytes(obj)
    except CanonViolation as exc:
        notes.append(f"{label}_digest_unavailable: {exc}")
        return None
    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest}"


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


def _validate_params(
    intervention: InterventionSpec,
    mech,
    issues: list[LinkIssue],
    *,
    path_prefix: list[str | int],
    ids: dict[str, str],
    allow_extra_params: bool,
    units_registry: UnitsRegistry | None,
    used_units: set[str],
    missing_registry_emitted: set[str],
    strict: bool,
) -> None:
    params = intervention.params
    spec_params = mech.params

    for param_id, spec in spec_params.items():
        value = _get_param_value(params, param_id)
        if value is None:
            if spec.required:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.MISSING_PARAM,
                        message=(
                            f"Missing required param '{param_id}' for '{mech.mechanism_id}'"
                        ),
                        path=path_prefix + [param_id],
                        ids=ids,
                    )
                )
            continue
        _validate_param_value(value, spec, issues, path_prefix + [param_id], ids)
        _validate_param_unit(
            value,
            spec,
            issues,
            path_prefix + [param_id],
            ids,
            units_registry,
            used_units=used_units,
            missing_registry_emitted=missing_registry_emitted,
            strict=strict,
        )

    if not allow_extra_params:
        for key in params.keys():
            if key not in spec_params:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.WARNING,
                        code=LinkIssueCode.UNKNOWN_PARAM,
                        message=f"Unknown param '{key}' for '{mech.mechanism_id}'",
                        path=path_prefix + [key],
                        ids=ids,
                    )
                )


def _validate_param_value(
    value: Any,
    spec,
    issues: list[LinkIssue],
    path: list[str | int],
    ids: dict[str, str],
) -> None:
    if spec.value_type == ParamType.BOOL and not isinstance(value, bool):
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.PARAM_TYPE,
                message=f"Param '{spec.param_id}' expects bool",
                path=path,
                ids=ids,
            )
        )
        return
    if spec.value_type == ParamType.STRING and not isinstance(value, str):
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.PARAM_TYPE,
                message=f"Param '{spec.param_id}' expects string",
                path=path,
                ids=ids,
            )
        )
        return
    if spec.value_type == ParamType.OBJECT and not isinstance(value, dict):
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.PARAM_TYPE,
                message=f"Param '{spec.param_id}' expects object",
                path=path,
                ids=ids,
            )
        )
        return
    if spec.value_type == ParamType.ARRAY and not isinstance(value, list):
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.PARAM_TYPE,
                message=f"Param '{spec.param_id}' expects array",
                path=path,
                ids=ids,
            )
        )
        return

    if spec.enum_values is not None:
        if value not in spec.enum_values:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.PARAM_ENUM,
                    message=f"Param '{spec.param_id}' must be one of {spec.enum_values}",
                    path=path,
                    ids=ids,
                )
            )
            return

    if spec.value_type == ParamType.RATE:
        numeric = _as_rate_decimal(value)
        if numeric is None:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.PARAM_TYPE,
                    message=f"Param '{spec.param_id}' expects rate value",
                    path=path,
                    ids=ids,
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
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.PARAM_TYPE,
                        message=f"Param '{spec.param_id}' expects numeric value",
                        path=path,
                        ids=ids,
                    )
                )
            return

    if spec.value_type in {ParamType.INT, ParamType.COUNT, ParamType.DURATION}:
        if numeric != numeric.to_integral_value():
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.PARAM_TYPE,
                    message=f"Param '{spec.param_id}' expects integer value",
                    path=path,
                    ids=ids,
                )
            )
            return

    if spec.min_value is not None and numeric < spec.min_value:
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.PARAM_RANGE,
                message=f"Param '{spec.param_id}' below min {spec.min_value}",
                path=path,
                ids=ids,
            )
        )
    if spec.max_value is not None and numeric > spec.max_value:
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.PARAM_RANGE,
                message=f"Param '{spec.param_id}' above max {spec.max_value}",
                path=path,
                ids=ids,
            )
        )


def _validate_param_unit(
    value: Any,
    spec,
    issues: list[LinkIssue],
    path: list[str | int],
    ids: dict[str, str],
    units_registry: UnitsRegistry | None,
    *,
    used_units: set[str],
    missing_registry_emitted: set[str],
    strict: bool,
) -> None:
    if spec.unit_id is None:
        return
    used_units.add(spec.unit_id)
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
    unit = units_registry.units.get(spec.unit_id)
    if unit is None:
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.UNKNOWN_UNIT,
                message=f"Unknown unit '{spec.unit_id}' for param '{spec.param_id}'",
                path=path + ["unit_id"],
                ids=ids,
                data={"unit_id": spec.unit_id, "where": "param"},
            )
        )
        return
    if spec.value_type == ParamType.MONEY:
        if not isinstance(unit, MoneyUnit):
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.UNIT_MISMATCH,
                    message=(
                        f"Param '{spec.param_id}' expects money unit '{spec.unit_id}'"
                    ),
                    path=path + ["unit_id"],
                    ids=ids,
                )
            )
            return
        if isinstance(value, MoneyValue):
            if value.currency != unit.currency:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.INCOMPATIBLE_CONSTRAINT,
                        message=(
                            f"Param '{spec.param_id}' currency '{value.currency}' does not "
                            f"match unit '{unit.currency}'"
                        ),
                        path=path,
                        ids=ids,
                        data={"expected": unit.currency, "actual": value.currency},
                    )
                )
        elif isinstance(value, (str, int, Decimal)) and spec.required:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.INCOMPATIBLE_CONSTRAINT,
                    message=f"Param '{spec.param_id}' requires MoneyValue with currency",
                    path=path,
                    ids=ids,
                )
            )
        return
    if spec.value_type == ParamType.RATE and not isinstance(unit, RateUnit):
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.UNIT_MISMATCH,
                message=f"Param '{spec.param_id}' expects rate unit '{spec.unit_id}'",
                path=path + ["unit_id"],
                ids=ids,
            )
        )
        return
    if spec.value_type == ParamType.RATE and isinstance(value, RateValue):
        if isinstance(unit, RateUnit) and value.base != unit.base:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.INCOMPATIBLE_CONSTRAINT,
                    message=(
                        f"Param '{spec.param_id}' rate base '{value.base}' does not match "
                        f"unit '{unit.base}'"
                    ),
                    path=path,
                    ids=ids,
                    data={"expected": unit.base, "actual": value.base},
                )
            )
    if spec.value_type == ParamType.DURATION and not isinstance(unit, DurationUnit):
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.UNIT_MISMATCH,
                message=(
                    f"Param '{spec.param_id}' expects duration unit '{spec.unit_id}'"
                ),
                path=path + ["unit_id"],
                ids=ids,
            )
        )
        return
    if spec.value_type == ParamType.COUNT and not isinstance(unit, CountUnit):
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.UNIT_MISMATCH,
                message=f"Param '{spec.param_id}' expects count unit '{spec.unit_id}'",
                path=path + ["unit_id"],
                ids=ids,
            )
        )


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
        else:
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

    if isinstance(unit, RateUnit) and isinstance(constraint.value, RateValue):
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
    "LinkedIntervention",
    "LinkedTrinityBundle",
    "TrinityBindings",
    "link_trinity",
]
