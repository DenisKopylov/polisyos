"""Builtin Foundry method components exposed through the extension path."""

from __future__ import annotations

from collections.abc import Iterator
from importlib import import_module
from typing import Any

from polisyos.foundry.extensions.api import FoundryMethodPlugin, component_for_method
from polisyos.foundry.methods.discovery import is_foundry_method

_BUILTIN_FAMILIES: dict[str, str] = {
    "bayesian": "register_bayesian_methods",
    "causal": "register_causal_methods",
    "dependence": "register_dependence_methods",
    "distributional": "register_distributional_methods",
    "econometrics": "register_econometric_methods",
    "forecasting": "register_forecasting_methods",
    "mechanism": "register_mechanism_methods",
    "microsim": "register_microsim_methods",
    "ml": "register_ml_methods",
    "network": "register_network_methods",
    "optimization": "register_optimization_methods",
    "policy": "register_policy_methods",
    "sensitivity": "register_sensitivity_methods",
    "simulation": "register_simulation_methods",
    "spatial": "register_spatial_methods",
    "survey": "register_survey_methods",
    "validation": "register_validation_methods",
}


def builtin_foundry_method_components(
    families: list[str] | tuple[str, ...] | None = None,
) -> tuple[FoundryMethodPlugin, ...]:
    """Return builtin method components without mutating a method registry."""
    selected = tuple(families or _BUILTIN_FAMILIES.keys())
    components: list[FoundryMethodPlugin] = []
    seen: set[str] = set()

    for family in selected:
        for method_class in _iter_family_method_classes(family):
            signature = method_class.signature
            if signature.fqn in seen:
                continue
            seen.add(signature.fqn)
            components.append(
                component_for_method(
                    method_class,
                    domains=[signature.namespace.split(".", 1)[0]],
                    tags={"builtin", f"family:{family}"},
                )
            )

    return tuple(sorted(components, key=lambda item: str(item.metadata.component_id)))


def _iter_family_method_classes(family: str) -> Iterator[type[Any]]:
    if family not in _BUILTIN_FAMILIES:
        raise ValueError(f"Unknown builtin Foundry method family: {family!r}")

    module_name = family
    module = import_module(f"polisyos.foundry.methods.catalog.{module_name}._registry_boot")
    register_name = _BUILTIN_FAMILIES[family]
    register = getattr(module, register_name)
    for method_class in register():
        if is_foundry_method(method_class):
            yield method_class


__all__ = ["builtin_foundry_method_components"]
