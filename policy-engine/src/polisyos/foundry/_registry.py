"""Public foundry registry module API."""

import importlib
import inspect
from collections.abc import Iterator, Mapping
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from typing import Any

from polisyos.foundry.contracts.fidelity import FidelityLevel as RuntimeFidelityLevel
from polisyos.foundry.contracts.specs import (
    MECHANISM_SPECS,
    get_mechanism_spec,
    mechanism_catalog,
    validate_mechanism_params,
)
from polisyos.ir.kernel import MechanismTypeSpec
from polisyos.ir.model_spec import FidelityLevel as IRFidelityLevel


@dataclass(frozen=True)
class MechanismRuntimeDescriptor:
    """Mechanism runtime descriptor data model."""

    mechanism_type: str
    method_fqn: str
    mechanism_class_path: str
    supported_fidelities: frozenset[RuntimeFidelityLevel]
    hybrid_default: RuntimeFidelityLevel

    @property
    def mechanism_class(self) -> type[Any]:
        mechanism_class = _load_symbol(self.mechanism_class_path)
        if not inspect.isclass(mechanism_class):
            raise TypeError(
                "Runtime mechanism descriptor resolved a non-class object for "
                f"'{self.mechanism_type}': {self.mechanism_class_path}"
            )
        return mechanism_class


_ALL_RUNTIME_FIDELITIES = frozenset(RuntimeFidelityLevel)


class _MechanismRegistryView(MappingABC[str, MechanismRuntimeDescriptor]):
    """Compatibility view backed by the unified mechanism method catalog."""

    def _mapping(self) -> dict[str, MechanismRuntimeDescriptor]:
        return _runtime_registry_descriptors()

    def __getitem__(self, key: str) -> MechanismRuntimeDescriptor:
        return self._mapping()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._mapping())

    def __len__(self) -> int:
        return len(self._mapping())


MECHANISM_REGISTRY: MappingABC[str, MechanismRuntimeDescriptor] = _MechanismRegistryView()


class MissingRuntimeMechanismSupportError(ValueError):
    """Raised when a mechanism exists in IR but has no executable Foundry runtime."""

    def __init__(self, mech_type: str) -> None:
        self.mech_type = str(mech_type)
        available = ", ".join(sorted(MECHANISM_REGISTRY))
        super().__init__(
            "Mechanism is registered in IR but not executable in Foundry runtime: "
            f"'{self.mech_type}'. Available runtime mechanisms: [{available}]"
        )


class UnsupportedRuntimeFidelityError(ValueError):
    """Raised when a runtime mechanism does not support requested fidelity."""

    def __init__(
        self,
        mech_type: str,
        requested: RuntimeFidelityLevel,
        supported: frozenset[RuntimeFidelityLevel],
    ) -> None:
        supported_labels = ", ".join(sorted(item.value for item in supported))
        super().__init__(
            "Unsupported runtime fidelity for mechanism "
            f"'{mech_type}': '{requested.value}' not in [{supported_labels}]"
        )


def has_runtime_mechanism_support(mech_type: str) -> bool:
    """Return whether has runtime mechanism support."""
    return mech_type in _runtime_registry_descriptors()


def get_mechanism_descriptor(mech_type: str) -> MechanismRuntimeDescriptor:
    """Return mechanism descriptor."""
    descriptors = _runtime_registry_descriptors()
    if mech_type not in descriptors:
        raise MissingRuntimeMechanismSupportError(mech_type)
    return descriptors[mech_type]


def get_mechanism_class(mech_type: str) -> type[Any]:
    """Return mechanism class."""
    return get_mechanism_descriptor(mech_type).mechanism_class


def resolve_runtime_fidelity(
    mech_type: str,
    requested_fidelity: IRFidelityLevel | str | None,
) -> RuntimeFidelityLevel:
    """Resolve runtime fidelity."""
    descriptor = get_mechanism_descriptor(mech_type)
    requested = (
        requested_fidelity
        if isinstance(requested_fidelity, IRFidelityLevel)
        else IRFidelityLevel(requested_fidelity or IRFidelityLevel.HYBRID.value)
    )

    if requested == IRFidelityLevel.SURROGATE_FLUID:
        resolved = RuntimeFidelityLevel.SURROGATE_FLUID
    elif requested == IRFidelityLevel.SURROGATE_DISCRETE:
        resolved = RuntimeFidelityLevel.RELAXED_DISCRETE
    elif requested == IRFidelityLevel.FULL_DISCRETE:
        resolved = RuntimeFidelityLevel.HARD_DISCRETE
    else:
        resolved = descriptor.hybrid_default

    if resolved not in descriptor.supported_fidelities:
        raise UnsupportedRuntimeFidelityError(
            mech_type,
            requested=resolved,
            supported=descriptor.supported_fidelities,
        )
    return resolved


def _init_kwargs(mech_cls: type[Any], kwargs: dict[str, Any]) -> dict[str, Any]:
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


def create_mechanism(
    intervention: Any,
    n_agents: int,
    n_firms: int = 0,
    *,
    selected_fidelity: RuntimeFidelityLevel | str | None = None,
) -> Any:
    """Create mechanism."""
    mechanism_type, params = _extract_intervention_fields(intervention)
    validate_mechanism_params(mechanism_type, params)
    descriptor = get_mechanism_descriptor(mechanism_type)
    runtime_fidelity = _coerce_runtime_fidelity(selected_fidelity) or descriptor.hybrid_default
    mech_cls = descriptor.mechanism_class
    init_kwargs = {
        "n_agents": n_agents,
        "n_firms": n_firms,
        "fidelity": runtime_fidelity,
        **params,
    }
    return mech_cls(**_init_kwargs(mech_cls, init_kwargs))


def create_mechanism_from_spec(
    mechanism_type: str,
    params: dict[str, Any],
    n_agents: int,
    n_firms: int = 0,
    *,
    mechanism_spec: MechanismTypeSpec | None = None,
    selected_fidelity: RuntimeFidelityLevel | str | None = None,
) -> Any:
    """Create mechanism from spec."""
    coerced = _coerce_params(params)
    validate_mechanism_params(mechanism_type, coerced, mechanism_spec=mechanism_spec)
    descriptor = get_mechanism_descriptor(mechanism_type)
    runtime_fidelity = _coerce_runtime_fidelity(selected_fidelity) or descriptor.hybrid_default
    mech_cls = descriptor.mechanism_class
    init_kwargs = {
        "n_agents": n_agents,
        "n_firms": n_firms,
        "fidelity": runtime_fidelity,
        **coerced,
    }
    return mech_cls(**_init_kwargs(mech_cls, init_kwargs))


def _coerce_runtime_fidelity(
    value: RuntimeFidelityLevel | str | None,
) -> RuntimeFidelityLevel | None:
    if value is None:
        return None
    if isinstance(value, RuntimeFidelityLevel):
        return value
    return RuntimeFidelityLevel(str(value))


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


def _extract_intervention_fields(intervention: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(intervention, Mapping):
        mechanism_type = intervention.get("mechanism_type") or intervention.get("kind")
        params = intervention.get("parameters") or intervention.get("params") or {}
    else:
        mechanism_type = getattr(intervention, "mechanism_type", None) or getattr(
            intervention, "kind", None
        )
        params = (
            getattr(intervention, "parameters", None) or getattr(intervention, "params", None) or {}
        )
    if not mechanism_type:
        raise ValueError("Intervention missing mechanism_type/kind")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError("Intervention params must be a dict")
    return mechanism_type, params


def _runtime_registry_descriptors() -> dict[str, MechanismRuntimeDescriptor]:
    from polisyos.foundry.methods.base import MethodKind
    from polisyos.foundry.methods.catalog.mechanism import ensure_mechanism_methods_registered
    from polisyos.foundry.methods.registry import MethodRegistry

    registry = MethodRegistry.get_instance()
    ensure_mechanism_methods_registered(registry)

    descriptors: dict[str, MechanismRuntimeDescriptor] = {}
    for signature in registry.list_all():
        if signature.kind is not MethodKind.MECHANISM:
            continue
        method_class = registry.get(signature.fqn)
        mechanism_type = str(getattr(method_class, "runtime_mechanism_type", "")).strip()
        mechanism_class_path = str(
            getattr(method_class, "runtime_mechanism_class_path", "")
        ).strip()
        if not mechanism_type or not mechanism_class_path:
            continue
        supported = _coerce_supported_fidelities(
            getattr(method_class, "supported_runtime_fidelities", _ALL_RUNTIME_FIDELITIES)
        )
        hybrid_default = _coerce_runtime_fidelity_value(
            getattr(
                method_class,
                "hybrid_default_runtime_fidelity",
                RuntimeFidelityLevel.SURROGATE_FLUID,
            )
        )
        descriptors[mechanism_type] = MechanismRuntimeDescriptor(
            mechanism_type=mechanism_type,
            method_fqn=signature.fqn,
            mechanism_class_path=mechanism_class_path,
            supported_fidelities=supported,
            hybrid_default=hybrid_default,
        )
    return {key: descriptors[key] for key in sorted(descriptors)}


def _coerce_supported_fidelities(values: Any) -> frozenset[RuntimeFidelityLevel]:
    if isinstance(values, RuntimeFidelityLevel):
        return frozenset({values})
    if isinstance(values, str):
        return frozenset({RuntimeFidelityLevel(str(values))})
    try:
        return frozenset(_coerce_runtime_fidelity_value(item) for item in values)
    except TypeError:
        return _ALL_RUNTIME_FIDELITIES


def _coerce_runtime_fidelity_value(value: Any) -> RuntimeFidelityLevel:
    if isinstance(value, RuntimeFidelityLevel):
        return value
    return RuntimeFidelityLevel(str(value))


def _load_symbol(path: str) -> Any:
    module_name, separator, symbol_name = str(path).partition(":")
    if not separator or not module_name or not symbol_name:
        raise ValueError(f"Invalid symbol path: {path!r}")
    module = importlib.import_module(module_name)
    return getattr(module, symbol_name)


__all__ = [
    "MECHANISM_REGISTRY",
    "MECHANISM_SPECS",
    "MechanismRuntimeDescriptor",
    "MissingRuntimeMechanismSupportError",
    "UnsupportedRuntimeFidelityError",
    "create_mechanism",
    "create_mechanism_from_spec",
    "get_mechanism_class",
    "get_mechanism_descriptor",
    "get_mechanism_spec",
    "has_runtime_mechanism_support",
    "mechanism_catalog",
    "resolve_runtime_fidelity",
    "validate_mechanism_params",
]
