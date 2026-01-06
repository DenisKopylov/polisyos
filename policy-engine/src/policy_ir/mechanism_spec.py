from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field


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
