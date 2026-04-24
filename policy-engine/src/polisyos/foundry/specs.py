"""Public foundry specs module API."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from polisyos.ir.kernel import DEFAULT_MECHANISM_REGISTRY, MechanismTypeSpec, ParamType
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.ir.units import UNIT_REGISTRY

MechanismSpec = MechanismTypeSpec
MECHANISM_SPECS: dict[str, MechanismSpec] = DEFAULT_MECHANISM_REGISTRY.mechanisms


def get_mechanism_spec(mech_type: str) -> MechanismSpec:
    """Return mechanism spec."""
    if mech_type not in MECHANISM_SPECS:
        raise ValueError(
            f"Unknown mechanism type: '{mech_type}'. Available: {list(MECHANISM_SPECS.keys())}"
        )
    return MECHANISM_SPECS[mech_type]


def _get_param_value(params: dict[str, Any], path: str) -> Any:
    current: Any = params
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _as_decimal(value: Any, *, percent_ok: bool = False) -> Decimal | None:
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
    if isinstance(value, float):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        if percent_ok and text.endswith("%"):
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


def _validate_param_value(value: Any, spec) -> None:
    if spec.value_type == ParamType.BOOL:
        if not isinstance(value, bool):
            raise ValueError(f"Mechanism param '{spec.param_id}' expects bool")
        return
    if spec.value_type == ParamType.STRING:
        if not isinstance(value, str):
            raise ValueError(f"Mechanism param '{spec.param_id}' expects string")
        return
    if spec.value_type == ParamType.OBJECT:
        if not isinstance(value, dict):
            raise ValueError(f"Mechanism param '{spec.param_id}' expects object")
        return
    if spec.value_type == ParamType.ARRAY:
        if not isinstance(value, list):
            raise ValueError(f"Mechanism param '{spec.param_id}' expects array")
        return

    if spec.enum_values is not None:
        if value not in spec.enum_values:
            raise ValueError(f"Mechanism param '{spec.param_id}' must be one of {spec.enum_values}")
        return

    numeric = _as_decimal(value, percent_ok=(spec.value_type == ParamType.RATE))
    if numeric is None:
        raise ValueError(f"Mechanism param '{spec.param_id}' expects {spec.value_type.value} value")

    if spec.value_type in {ParamType.INT, ParamType.COUNT, ParamType.DURATION}:
        if numeric != numeric.to_integral_value():
            raise ValueError(f"Mechanism param '{spec.param_id}' expects integer value")

    if spec.min_value is not None and numeric < spec.min_value:
        raise ValueError(f"Mechanism param '{spec.param_id}' below min {spec.min_value}")
    if spec.max_value is not None and numeric > spec.max_value:
        raise ValueError(f"Mechanism param '{spec.param_id}' above max {spec.max_value}")


def validate_mechanism_params(
    mech_type: str,
    params: dict[str, Any],
    *,
    allow_extra_params: bool = False,
    mechanism_spec: MechanismSpec | None = None,
) -> None:
    """Validate mechanism params."""
    spec = mechanism_spec or get_mechanism_spec(mech_type)
    spec_params = spec.params

    missing = [
        param_id
        for param_id, param_spec in spec_params.items()
        if param_spec.required and _get_param_value(params, param_id) is None
    ]
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Mechanism '{mech_type}' requires params: {missing_list}")

    for param_id, param_spec in spec_params.items():
        value = _get_param_value(params, param_id)
        if value is None:
            continue
        _validate_param_value(value, param_spec)
        if param_spec.unit_id and param_spec.unit_id not in UNIT_REGISTRY:
            raise ValueError(
                f"Mechanism '{mech_type}' param '{param_id}' uses unknown unit "
                f"'{param_spec.unit_id}'"
            )

    if not allow_extra_params:
        for key in params:
            if key not in spec_params:
                raise ValueError(f"Mechanism '{mech_type}' has unknown param '{key}'")


def mechanism_catalog() -> list[dict]:
    """Mechanism catalog helper."""
    catalog = []
    for name, spec in sorted(MECHANISM_SPECS.items()):
        required = [param_id for param_id, param in spec.params.items() if param.required]
        ranges = {
            param_id: (param.min_value, param.max_value)
            for param_id, param in spec.params.items()
            if param.min_value is not None or param.max_value is not None
        }
        units = {
            param_id: param.unit_id
            for param_id, param in spec.params.items()
            if param.unit_id is not None
        }
        catalog.append(
            {
                "name": name,
                "required_params": sorted(required),
                "param_ranges": ranges,
                "param_units": units,
                "description": spec.description,
            }
        )
    return catalog
