"""Parameter validation helpers for Trinity linker."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from polisyos.ir.kernel.mechanisms import ParamType
from polisyos.ir.kernel.units import (
    CountUnit,
    DurationUnit,
    MoneyUnit,
    RateUnit,
    UnitsRegistry,
)
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue

from .reports import LinkIssue, LinkIssueCode, LinkSeverity

if TYPE_CHECKING:
    from polisyos.ir.governance.policy_spec import InterventionSpec
    from polisyos.ir.kernel.mechanisms import MechanismTypeSpec, ParamSpec

_MISSING_PARAM = object()
MAX_PARAM_PATH_DEPTH = 16


class _ParamPathError(ValueError):
    def __init__(self, *, path: str, message: str) -> None:
        self.path = path
        super().__init__(message)


def _validate_param_structure(
    value: Any,
    issues: list[LinkIssue],
    *,
    path: list[str | int],
    ids: dict[str, str],
    depth: int = 0,
) -> None:
    if depth > MAX_PARAM_PATH_DEPTH:
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.PARAM_PATH,
                message=(f"Parameter payload nesting exceeds max depth {MAX_PARAM_PATH_DEPTH}"),
                path=path,
                ids=ids,
                data={"max_depth": MAX_PARAM_PATH_DEPTH},
            )
        )
        return
    if isinstance(value, dict):
        for key in sorted(value):
            if "." in key:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.PARAM_PATH,
                        message=(
                            "Dots in parameter field names are not supported; "
                            "use nested objects with dot-separated ParamSpec.param_id"
                        ),
                        path=[*path, key],
                        ids=ids,
                    )
                )
                continue
            _validate_param_structure(
                value[key],
                issues,
                path=[*path, key],
                ids=ids,
                depth=depth + 1,
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, (dict, list)):
                _validate_param_structure(
                    item,
                    issues,
                    path=[*path, index],
                    ids=ids,
                    depth=depth + 1,
                )


def _get_param_value(params: dict[str, Any], path: str) -> Any:
    if not path or path.startswith(".") or path.endswith(".") or ".." in path:
        raise _ParamPathError(path=path, message=f"Invalid param path '{path}'")
    parts = path.split(".")
    if len(parts) > MAX_PARAM_PATH_DEPTH:
        raise _ParamPathError(
            path=path,
            message=f"Param path exceeds max depth {MAX_PARAM_PATH_DEPTH}",
        )
    current: Any = params
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return _MISSING_PARAM
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
    mech: MechanismTypeSpec,
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
    _validate_param_structure(
        params,
        issues,
        path=path_prefix,
        ids=ids,
    )

    for param_id, spec in spec_params.items():
        try:
            value = _get_param_value(params, param_id)
        except _ParamPathError as exc:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.PARAM_PATH,
                    message=str(exc),
                    path=[*path_prefix, param_id],
                    ids=ids,
                    data={"param_path": exc.path},
                )
            )
            continue
        if value is _MISSING_PARAM:
            if spec.required:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.MISSING_PARAM,
                        message=(f"Missing required param '{param_id}' for '{mech.mechanism_id}'"),
                        path=[*path_prefix, param_id],
                        ids=ids,
                    )
                )
            continue
        _validate_param_value(value, spec, issues, [*path_prefix, param_id], ids)
        _validate_param_unit(
            value,
            spec,
            issues,
            [*path_prefix, param_id],
            ids,
            units_registry,
            used_units=used_units,
            missing_registry_emitted=missing_registry_emitted,
            strict=strict,
        )

    if not allow_extra_params:
        for key in params:
            if key not in spec_params:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.WARNING,
                        code=LinkIssueCode.UNKNOWN_PARAM,
                        message=f"Unknown param '{key}' for '{mech.mechanism_id}'",
                        path=[*path_prefix, key],
                        ids=ids,
                    )
                )


def _validate_param_value(
    value: Any,
    spec: ParamSpec,
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

    if spec.enum_values is not None and value not in spec.enum_values:
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
    spec: ParamSpec,
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
                path=[*path, "unit_id"],
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
                    message=(f"Param '{spec.param_id}' expects money unit '{spec.unit_id}'"),
                    path=[*path, "unit_id"],
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
                path=[*path, "unit_id"],
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
                message=(f"Param '{spec.param_id}' expects duration unit '{spec.unit_id}'"),
                path=[*path, "unit_id"],
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
                path=[*path, "unit_id"],
                ids=ids,
            )
        )


__all__ = [
    "MAX_PARAM_PATH_DEPTH",
    "_as_decimal",
    "_as_rate_decimal",
    "_get_param_value",
    "_validate_param_structure",
    "_validate_param_unit",
    "_validate_param_value",
    "_validate_params",
]
