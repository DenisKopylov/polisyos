from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Annotated

from polisyos.ir.kernel.base import (
    ARTIFACT_ID_PATTERN,
    ID_PATTERN,
    KernelModel,
    reject_floats_deep,
)
from polisyos.ir.kernel.mechanisms import MechanismTypeRegistry, ParamSpec, ParamType
from polisyos.ir.kernel.numbers import DecimalValue, NonNegativeDecimal
from polisyos.ir.kernel.time_semantics import TimeSemantics
from polisyos.ir.kernel.units import MoneyUnit, RateUnit, UnitsRegistry
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.ir.types import (
    EntityType,
    OptimizationDirection,
    SelectorOperator,
    TranslatableString,
)

MAX_SELECTOR_DEPTH = 6
MAX_SELECTOR_NODES = 200
MAX_SELECTOR_CLAUSES = 50
MAX_INTERVENTIONS = 200
MAX_OBJECTIVES = 50
MAX_CONSTRAINTS = 100

SelectorScalar = str | int | bool | DecimalValue
SelectorValue = SelectorScalar | list[SelectorScalar]

ParamValue = Annotated[
    Any,
    BeforeValidator(reject_floats_deep),
]


class SelectorPredicate(KernelModel):
    kind: Literal["predicate"] = "predicate"
    field: str = Field(..., max_length=64)
    operator: SelectorOperator
    value: SelectorValue

    @model_validator(mode="after")
    def validate_value(self) -> "SelectorPredicate":
        if self.operator in {SelectorOperator.IN, SelectorOperator.NOT_IN}:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError("operator 'in' requires a non-empty list")
        if self.operator == SelectorOperator.BETWEEN:
            if not isinstance(self.value, list) or len(self.value) != 2:
                raise ValueError("operator 'between' requires a list of two values")
        if self.operator == SelectorOperator.CONTAINS:
            if not isinstance(self.value, (str, list)):
                raise ValueError("operator 'contains' requires string or list value")
        return self


class SelectorAll(KernelModel):
    kind: Literal["all_of"] = "all_of"
    clauses: list["SelectorExpr"]


class SelectorAny(KernelModel):
    kind: Literal["any_of"] = "any_of"
    clauses: list["SelectorExpr"]


class SelectorNot(KernelModel):
    kind: Literal["not"] = "not"
    clause: "SelectorExpr"


SelectorExpr = Annotated[
    SelectorPredicate | SelectorAll | SelectorAny | SelectorNot,
    Field(discriminator="kind"),
]


class ScheduleSpec(KernelModel):
    start_step: int = Field(..., ge=0)
    end_step: int | None = Field(None, ge=0)
    duration_steps: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def validate_schedule(self) -> "ScheduleSpec":
        if self.end_step is None and self.duration_steps is None:
            raise ValueError("end_step or duration_steps must be provided")
        if self.end_step is not None and self.end_step < self.start_step:
            raise ValueError("end_step must be >= start_step")
        if self.end_step is not None and self.duration_steps is not None:
            expected = self.end_step - self.start_step + 1
            if expected != self.duration_steps:
                raise ValueError("end_step and duration_steps mismatch")
        return self


class InterventionSpec(KernelModel):
    intervention_id: str = Field(..., pattern=ID_PATTERN)
    kind: str = Field(..., pattern=ID_PATTERN)
    target: SelectorExpr
    schedule: ScheduleSpec
    params: dict[str, ParamValue] = Field(default_factory=dict)
    priority: int | None = Field(None, ge=0)
    notes: list[str] = Field(default_factory=list)


class ObjectiveSpec(KernelModel):
    objective_id: str = Field(..., pattern=ID_PATTERN)
    metric_id: str = Field(..., pattern=ID_PATTERN)
    direction: OptimizationDirection
    target: DecimalValue | None = None
    weight: NonNegativeDecimal = Decimal("1")


class ConstraintSpec(KernelModel):
    constraint_id: str = Field(..., pattern=ID_PATTERN)
    value: MoneyValue | RateValue | CountValue | DurationValue | DecimalValue | int | str | bool
    notes: list[str] = Field(default_factory=list)


class PolicySemantic(KernelModel):
    context_snapshot_ref: str = Field(..., pattern=ARTIFACT_ID_PATTERN)
    registry_bundle_ref: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    time_semantics: TimeSemantics | None = None
    objectives: list[ObjectiveSpec] = Field(default_factory=list)
    interventions: list[InterventionSpec] = Field(default_factory=list)
    constraints: list[ConstraintSpec] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_limits(self) -> "PolicySemantic":
        if len(self.interventions) > MAX_INTERVENTIONS:
            raise ValueError("too many interventions")
        if len(self.objectives) > MAX_OBJECTIVES:
            raise ValueError("too many objectives")
        if len(self.constraints) > MAX_CONSTRAINTS:
            raise ValueError("too many constraints")
        _validate_selector_limits(self.interventions)
        _validate_unique_ids(self.objectives, "objective_id")
        _validate_unique_ids(self.interventions, "intervention_id")
        _validate_unique_ids(self.constraints, "constraint_id")
        return self

    def semantic_payload(
        self,
        *,
        mechanism_registry: MechanismTypeRegistry | None = None,
        units_registry: UnitsRegistry | None = None,
    ) -> dict[str, Any]:
        return {
            "context_snapshot_ref": self.context_snapshot_ref,
            "registry_bundle_ref": self.registry_bundle_ref,
            "time_semantics": self.time_semantics.model_dump() if self.time_semantics else None,
            "objectives": _canonical_objectives(self.objectives),
            "interventions": _canonical_interventions(
                self.interventions,
                mechanism_registry=mechanism_registry,
                units_registry=units_registry,
            ),
            "constraints": _canonical_constraints(self.constraints),
        }


class AdvisoryEntity(KernelModel):
    entity_id: str = Field(..., pattern=ID_PATTERN)
    entity_type: EntityType
    name: TranslatableString | None = None
    parent_id: str | None = Field(None, pattern=ID_PATTERN)
    attributes: dict[str, str | int | bool] = Field(default_factory=dict)


class PolicyAdvisory(KernelModel):
    entities: list[AdvisoryEntity] = Field(default_factory=list)
    narrative: str | None = Field(None, max_length=2000)
    labels: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PolicySurfaceIR(KernelModel):
    schema_version: str = Field("2.0", pattern=r"^\d+\.\d+$")
    semantic: PolicySemantic
    advisory: PolicyAdvisory | None = None

    def semantic_fingerprint_payload(
        self,
        *,
        mechanism_registry: MechanismTypeRegistry | None = None,
        units_registry: UnitsRegistry | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "semantic": self.semantic.semantic_payload(
                mechanism_registry=mechanism_registry,
                units_registry=units_registry,
            ),
        }


def _sorted_dump(items: list[KernelModel], key: str) -> list[dict[str, Any]]:
    return [item.model_dump() for item in sorted(items, key=lambda x: getattr(x, key))]


def _validate_unique_ids(items: list[KernelModel], attr: str) -> None:
    seen: set[str] = set()
    for item in items:
        value = getattr(item, attr)
        if value in seen:
            raise ValueError(f"duplicate {attr}: {value}")
        seen.add(value)


def _selector_stats(node: SelectorExpr) -> tuple[int, int]:
    if isinstance(node, SelectorPredicate):
        return 1, 1
    if isinstance(node, SelectorNot):
        depth, nodes = _selector_stats(node.clause)
        return depth + 1, nodes + 1
    if isinstance(node, (SelectorAll, SelectorAny)):
        depths = []
        total = 1
        for clause in node.clauses:
            depth, nodes = _selector_stats(clause)
            depths.append(depth)
            total += nodes
        return (max(depths) + 1 if depths else 1), total
    return 1, 1


def _validate_selector_limits(interventions: list[InterventionSpec]) -> None:
    for intervention in interventions:
        depth, nodes = _selector_stats(intervention.target)
        if depth > MAX_SELECTOR_DEPTH:
            raise ValueError(f"selector depth {depth} exceeds limit {MAX_SELECTOR_DEPTH}")
        if nodes > MAX_SELECTOR_NODES:
            raise ValueError(f"selector nodes {nodes} exceeds limit {MAX_SELECTOR_NODES}")
        if isinstance(intervention.target, (SelectorAll, SelectorAny)):
            if len(intervention.target.clauses) > MAX_SELECTOR_CLAUSES:
                raise ValueError("selector clause count exceeds limit")


def schedule_range(schedule: ScheduleSpec) -> tuple[int, int]:
    start = schedule.start_step
    if schedule.end_step is None:
        end = start + int(schedule.duration_steps or 0) - 1
    else:
        end = schedule.end_step
    return start, end


def _schedule_payload(schedule: ScheduleSpec) -> dict[str, int]:
    start, end = schedule_range(schedule)
    duration = schedule.duration_steps if schedule.duration_steps is not None else end - start + 1
    return {
        "start_step": start,
        "end_step": end,
        "duration_steps": int(duration),
    }


def _normalize_decimal(value: Decimal) -> Decimal:
    text = format(value.normalize(), "f")
    if text == "-0":
        text = "0"
    return Decimal(text)


def _canonicalize_selector_value(value: SelectorValue) -> SelectorValue:
    if isinstance(value, list):
        return [_canonicalize_selector_value(item) for item in value]  # type: ignore[list-item]
    if isinstance(value, Decimal):
        return _normalize_decimal(value)  # type: ignore[return-value]
    return value


def _canonicalize_selector_expr(node: SelectorExpr) -> dict[str, Any]:
    if isinstance(node, SelectorPredicate):
        return {
            "kind": node.kind,
            "field": node.field,
            "operator": node.operator.value,
            "value": _canonicalize_selector_value(node.value),
        }
    if isinstance(node, SelectorNot):
        return {"kind": node.kind, "clause": _canonicalize_selector_expr(node.clause)}
    if isinstance(node, SelectorAll):
        return {
            "kind": node.kind,
            "clauses": [_canonicalize_selector_expr(c) for c in node.clauses],
        }
    if isinstance(node, SelectorAny):
        return {
            "kind": node.kind,
            "clauses": [_canonicalize_selector_expr(c) for c in node.clauses],
        }
    return node.model_dump()


def _canonicalize_money_value(value: MoneyValue) -> dict[str, Any]:
    return {
        "amount": _normalize_decimal(value.amount),
        "currency": value.currency,
        "nominal_year": value.nominal_year,
    }


def _canonicalize_rate_value(value: RateValue) -> dict[str, Any]:
    return {"value": _normalize_decimal(value.as_ratio()), "base": "ratio"}


def _canonicalize_value(value: Any) -> Any:
    if isinstance(value, MoneyValue):
        return _canonicalize_money_value(value)
    if isinstance(value, RateValue):
        return _canonicalize_rate_value(value)
    if isinstance(value, CountValue):
        return value.model_dump()
    if isinstance(value, DurationValue):
        return value.model_dump()
    if isinstance(value, Decimal):
        return _normalize_decimal(value)
    if isinstance(value, list):
        return [_canonicalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonicalize_value(val) for key, val in value.items()}
    return value


def _parse_decimal(value: Any) -> Decimal | None:
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
            return Decimal(value.strip())
        except InvalidOperation:
            return None
    return None


def _parse_rate(value: Any, *, assume_percent: bool) -> Decimal | None:
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
            numeric = Decimal(text)
        except InvalidOperation:
            return None
        if assume_percent:
            return numeric / Decimal("100")
        return numeric
    return None


def _normalize_param_value(
    value: Any,
    spec: ParamSpec,
    units_registry: UnitsRegistry | None,
) -> Any:
    if spec.value_type == ParamType.RATE:
        assume_percent = False
        if spec.unit_id and units_registry:
            unit = units_registry.units.get(spec.unit_id)
            if isinstance(unit, RateUnit) and unit.base == "percent":
                assume_percent = True
        numeric = _parse_rate(value, assume_percent=assume_percent)
        if numeric is None:
            return value
        return _normalize_decimal(numeric)

    if spec.value_type == ParamType.MONEY:
        if isinstance(value, MoneyValue):
            return MoneyValue(
                amount=_normalize_decimal(value.amount),
                currency=value.currency,
                nominal_year=value.nominal_year,
            )
        numeric = _parse_decimal(value)
        if numeric is None:
            return value
        unit = units_registry.units.get(spec.unit_id) if units_registry else None
        if isinstance(unit, MoneyUnit):
            return MoneyValue(
                amount=_normalize_decimal(numeric),
                currency=unit.currency,
                nominal_year=unit.nominal_year,
            )
        return _normalize_decimal(numeric)

    if spec.value_type in {ParamType.INT, ParamType.COUNT, ParamType.DURATION}:
        numeric = _parse_decimal(value)
        if numeric is None:
            return value
        try:
            int_value = int(numeric)
        except (ValueError, OverflowError):
            return value
        return int_value

    if spec.value_type in {ParamType.DECIMAL}:
        numeric = _parse_decimal(value)
        if numeric is None:
            return value
        return _normalize_decimal(numeric)

    return value


def _set_param_value(
    params: dict[str, Any],
    path: str,
    value: Any,
) -> dict[str, Any]:
    if "." not in path:
        params[path] = value
        return params
    head, tail = path.split(".", 1)
    current = params.get(head)
    if not isinstance(current, dict):
        current = {}
    params[head] = _set_param_value(dict(current), tail, value)
    return params


def _get_param_value(params: dict[str, Any], path: str) -> Any:
    current: Any = params
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _normalize_params_for_intervention(
    params: dict[str, ParamValue],
    kind: str,
    mechanism_registry: MechanismTypeRegistry | None,
    units_registry: UnitsRegistry | None,
) -> dict[str, Any]:
    if mechanism_registry is None:
        return params
    spec = mechanism_registry.mechanisms.get(kind)
    if spec is None or not spec.params:
        return params
    normalized = dict(params)
    for param_id, param_spec in spec.params.items():
        value = _get_param_value(params, param_id)
        if value is None:
            continue
        normalized_value = _normalize_param_value(value, param_spec, units_registry)
        normalized = _set_param_value(normalized, param_id, normalized_value)
    return normalized


def _canonicalize_params(
    params: dict[str, ParamValue],
    *,
    kind: str | None = None,
    mechanism_registry: MechanismTypeRegistry | None = None,
    units_registry: UnitsRegistry | None = None,
) -> dict[str, Any]:
    normalized = (
        _normalize_params_for_intervention(params, kind, mechanism_registry, units_registry)
        if kind and mechanism_registry
        else params
    )
    return {key: _canonicalize_value(val) for key, val in normalized.items()}


def _canonical_objective(obj: ObjectiveSpec) -> dict[str, Any]:
    target = obj.target
    if isinstance(target, Decimal):
        target = _normalize_decimal(target)
    return {
        "objective_id": obj.objective_id,
        "metric_id": obj.metric_id,
        "direction": obj.direction.value,
        "target": target,
        "weight": _normalize_decimal(obj.weight),
    }


def _canonical_objectives(items: list[ObjectiveSpec]) -> list[dict[str, Any]]:
    return [_canonical_objective(item) for item in sorted(items, key=lambda x: x.objective_id)]


def _canonical_constraint(item: ConstraintSpec) -> dict[str, Any]:
    return {
        "constraint_id": item.constraint_id,
        "value": _canonicalize_value(item.value),
        "notes": item.notes,
    }


def _canonical_constraints(items: list[ConstraintSpec]) -> list[dict[str, Any]]:
    return [_canonical_constraint(item) for item in sorted(items, key=lambda x: x.constraint_id)]


def _canonical_intervention(
    item: InterventionSpec,
    *,
    mechanism_registry: MechanismTypeRegistry | None,
    units_registry: UnitsRegistry | None,
) -> dict[str, Any]:
    return {
        "intervention_id": item.intervention_id,
        "kind": item.kind,
        "target": _canonicalize_selector_expr(item.target),
        "schedule": _schedule_payload(item.schedule),
        "params": _canonicalize_params(
            item.params,
            kind=item.kind,
            mechanism_registry=mechanism_registry,
            units_registry=units_registry,
        ),
        "priority": item.priority,
        "notes": item.notes,
    }


def _canonical_interventions(
    items: list[InterventionSpec],
    *,
    mechanism_registry: MechanismTypeRegistry | None,
    units_registry: UnitsRegistry | None,
) -> list[dict[str, Any]]:
    return [
        _canonical_intervention(
            item,
            mechanism_registry=mechanism_registry,
            units_registry=units_registry,
        )
        for item in sorted(items, key=lambda x: x.intervention_id)
    ]
