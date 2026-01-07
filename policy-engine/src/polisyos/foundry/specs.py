from __future__ import annotations

from typing import Dict, Optional, Set, Tuple, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.units import UNIT_REGISTRY


class MechanismSpec(BaseModel):
    name: str = Field(..., max_length=100)
    required_params: Set[str] = Field(default_factory=set)
    param_ranges: Dict[str, Tuple[float, float]] = Field(default_factory=dict)
    param_units: Dict[str, str] = Field(default_factory=dict)
    nested_params: Dict[str, "MechanismSpec"] = Field(default_factory=dict)
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


MECHANISM_SPECS: Dict[str, MechanismSpec] = {
    "tax_subsidy": MechanismSpec(
        name="tax_subsidy",
        required_params={"rate"},
        param_ranges={"rate": (0.0, 1.0)},
        param_units={"rate": "ratio"},
    ),
    "income_tax": MechanismSpec(
        name="income_tax",
        required_params={"rate"},
        param_ranges={"rate": (0.0, 1.0)},
        param_units={"rate": "ratio"},
    ),
    "queue": MechanismSpec(
        name="queue",
        required_params={"service_rate", "arrival_rate"},
        param_ranges={"service_rate": (0.0, 1e9), "arrival_rate": (0.0, 1e9)},
        param_units={"service_rate": "per_step", "arrival_rate": "per_step"},
    ),
}


def get_mechanism_spec(mech_type: str) -> MechanismSpec:
    if mech_type not in MECHANISM_SPECS:
        raise ValueError(
            f"Unknown mechanism type: '{mech_type}'. Available: {list(MECHANISM_SPECS.keys())}"
        )
    return MECHANISM_SPECS[mech_type]


def _get_param_value(params: Dict[str, Any], path: str) -> Any:
    current = params
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _validate_nested_specs(params: Dict[str, Any], spec: MechanismSpec) -> None:
    for key, nested_spec in spec.nested_params.items():
        nested_value = params.get(key)
        if not isinstance(nested_value, dict):
            raise ValueError(f"Mechanism '{spec.name}' param '{key}' must be object")
        missing = nested_spec.required_params - set(nested_value.keys())
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(
                f"Mechanism '{spec.name}.{key}' requires params: {missing_list}"
            )
        for nested_key, (min_val, max_val) in nested_spec.param_ranges.items():
            value = _get_param_value(nested_value, nested_key)
            if value is None:
                continue
            if isinstance(value, (int, float)) and (value < min_val or value > max_val):
                raise ValueError(
                    f"Mechanism '{spec.name}.{key}' param '{nested_key}' "
                    f"out of range [{min_val}, {max_val}]"
                )
        for nested_key, unit in nested_spec.param_units.items():
            if unit not in UNIT_REGISTRY:
                raise ValueError(
                    f"Mechanism '{spec.name}.{key}' param '{nested_key}' "
                    f"uses unknown unit '{unit}'"
                )


def validate_mechanism_params(mech_type: str, params: Dict[str, Any]) -> None:
    spec = get_mechanism_spec(mech_type)
    missing = spec.required_params - set(params.keys())
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Mechanism '{mech_type}' requires params: {missing_list}")
    for key, (min_val, max_val) in spec.param_ranges.items():
        value = _get_param_value(params, key)
        if value is None:
            continue
        if isinstance(value, (int, float)) and (value < min_val or value > max_val):
            raise ValueError(
                f"Mechanism '{mech_type}' param '{key}' out of range [{min_val}, {max_val}]"
            )
    for key, unit in spec.param_units.items():
        if unit not in UNIT_REGISTRY:
            raise ValueError(
                f"Mechanism '{mech_type}' param '{key}' uses unknown unit '{unit}'"
            )
    _validate_nested_specs(params, spec)


def mechanism_catalog() -> list[dict]:
    catalog = []
    for name, spec in sorted(MECHANISM_SPECS.items()):
        catalog.append(
            {
                "name": name,
                "required_params": sorted(spec.required_params),
                "param_ranges": spec.param_ranges,
                "param_units": spec.param_units,
                "description": spec.description,
            }
        )
    return catalog
