import inspect
from typing import Any, Dict, Type

from polisyos.foundry.base import Mechanism
from polisyos.foundry.fiscal import IncomeTax, TaxSubsidy
from polisyos.foundry.queue import QueueMechanism
from polisyos.foundry.specs import (
    MECHANISM_SPECS,
    get_mechanism_spec,
    mechanism_catalog,
    validate_mechanism_params,
)
from polisyos.ir.contract import Intervention

MECHANISM_REGISTRY: Dict[str, Type[Mechanism]] = {
    "tax_subsidy": TaxSubsidy,
    "income_tax": IncomeTax,
    "queue": QueueMechanism,
}


def get_mechanism_class(mech_type: str) -> Type[Mechanism]:
    if mech_type not in MECHANISM_REGISTRY:
        raise ValueError(
            f"Unknown mechanism type: '{mech_type}'. Available: {list(MECHANISM_REGISTRY.keys())}"
        )
    return MECHANISM_REGISTRY[mech_type]


def _init_kwargs(mech_cls: Type[Mechanism], kwargs: dict[str, Any]) -> dict[str, Any]:
    signature = inspect.signature(mech_cls.__init__)
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return kwargs
    accepted = {}
    for name in signature.parameters:
        if name == "self":
            continue
        if name in kwargs:
            accepted[name] = kwargs[name]
    return accepted


def create_mechanism(intervention: Intervention, n_agents: int, n_firms: int = 0) -> Mechanism:
    validate_mechanism_params(intervention.mechanism_type, intervention.parameters)
    mech_cls = get_mechanism_class(intervention.mechanism_type)
    init_kwargs = {
        "n_agents": n_agents,
        "n_firms": n_firms,
        **intervention.parameters,
    }
    return mech_cls(**_init_kwargs(mech_cls, init_kwargs))


def create_mechanism_from_spec(
    mechanism_type: str, params: dict[str, Any], n_agents: int, n_firms: int = 0
) -> Mechanism:
    coerced = _coerce_params(params)
    validate_mechanism_params(mechanism_type, coerced)
    mech_cls = get_mechanism_class(mechanism_type)
    init_kwargs = {
        "n_agents": n_agents,
        "n_firms": n_firms,
        **coerced,
    }
    return mech_cls(**_init_kwargs(mech_cls, init_kwargs))


def _coerce_params(value: Any) -> Any:
    from decimal import Decimal, InvalidOperation

    from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue

    if isinstance(value, RateValue):
        return float(value.as_ratio())
    if isinstance(value, MoneyValue):
        return float(value.amount)
    if isinstance(value, CountValue):
        return float(value.value)
    if isinstance(value, DurationValue):
        return float(value.value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        try:
            return float(Decimal(value))
        except InvalidOperation:
            return value
    if isinstance(value, list):
        return [_coerce_params(item) for item in value]
    if isinstance(value, dict):
        return {key: _coerce_params(val) for key, val in value.items()}
    return value


__all__ = [
    "MECHANISM_REGISTRY",
    "MECHANISM_SPECS",
    "create_mechanism",
    "create_mechanism_from_spec",
    "get_mechanism_class",
    "get_mechanism_spec",
    "mechanism_catalog",
    "validate_mechanism_params",
]
