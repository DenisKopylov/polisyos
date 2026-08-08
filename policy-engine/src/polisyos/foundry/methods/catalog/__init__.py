"""Lazy bootstrap for built-in Foundry method families."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from polisyos.foundry.extensions.registry import FoundryExtensionRegistryReport
from polisyos.foundry.methods.selection.registry import MethodRegistry

_FamilyBootstrap = Callable[[MethodRegistry | None], None]

_FAMILY_BOOTSTRAPS: dict[str, tuple[str, str]] = {
    "bayesian": ("bayesian", "ensure_bayesian_methods_registered"),
    "causal": ("causal", "ensure_causal_methods_registered"),
    "dependence": ("dependence", "ensure_dependence_methods_registered"),
    "distributional": ("distributional", "ensure_distributional_methods_registered"),
    "econometrics": ("econometrics", "ensure_econometric_methods_registered"),
    "forecasting": ("forecasting", "ensure_forecasting_methods_registered"),
    "mechanism": ("mechanism", "ensure_mechanism_methods_registered"),
    "microsim": ("microsim", "ensure_microsim_methods_registered"),
    "ml": ("ml", "ensure_ml_methods_registered"),
    "network": ("network", "ensure_network_methods_registered"),
    "optimization": ("optimization", "ensure_optimization_methods_registered"),
    "policy": ("policy", "ensure_policy_methods_registered"),
    "sensitivity": ("sensitivity", "ensure_sensitivity_methods_registered"),
    "simulation": ("simulation", "ensure_simulation_methods_registered"),
    "spatial": ("spatial", "ensure_spatial_methods_registered"),
    "survey": ("survey", "ensure_survey_methods_registered"),
    "validation": ("validation", "ensure_validation_methods_registered"),
}


def _load_bootstrap(family: str) -> _FamilyBootstrap | None:
    module_name, function_name = _FAMILY_BOOTSTRAPS[family]
    try:
        module = import_module(f"polisyos.foundry.methods.catalog.{module_name}")
    except ModuleNotFoundError:  # pragma: no cover - defensive for partial installs
        return None
    return getattr(module, function_name)


def _ensure_family_registered(family: str, registry: MethodRegistry | None = None) -> None:
    bootstrap = _load_bootstrap(family)
    if bootstrap is None:
        return
    bootstrap(registry)


def ensure_bayesian_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("bayesian", registry)


def ensure_causal_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("causal", registry)


def ensure_dependence_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("dependence", registry)


def ensure_distributional_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("distributional", registry)


def ensure_econometric_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("econometrics", registry)


def ensure_forecasting_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("forecasting", registry)


def ensure_mechanism_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("mechanism", registry)


def ensure_microsim_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("microsim", registry)


def ensure_ml_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("ml", registry)


def ensure_network_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("network", registry)


def ensure_optimization_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("optimization", registry)


def ensure_policy_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("policy", registry)


def ensure_sensitivity_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("sensitivity", registry)


def ensure_simulation_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("simulation", registry)


def ensure_spatial_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("spatial", registry)


def ensure_survey_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("survey", registry)


def ensure_validation_methods_registered(registry: MethodRegistry | None = None) -> None:
    _ensure_family_registered("validation", registry)


def ensure_all_methods_registered(
    registry: MethodRegistry | None = None,
) -> FoundryExtensionRegistryReport:
    """Register installed Foundry method extensions into `registry` or the singleton."""
    from polisyos.foundry.extensions.registry import bootstrap_foundry_method_registry

    return bootstrap_foundry_method_registry(
        registry if registry is not None else MethodRegistry.get_instance(),
        include_builtins=True,
        include_entry_points=True,
        include_dev_scan=True,
        require_bound_discovery_manifest=False,
    )


__all__ = [
    "ensure_all_methods_registered",
    "ensure_bayesian_methods_registered",
    "ensure_causal_methods_registered",
    "ensure_dependence_methods_registered",
    "ensure_distributional_methods_registered",
    "ensure_econometric_methods_registered",
    "ensure_forecasting_methods_registered",
    "ensure_mechanism_methods_registered",
    "ensure_microsim_methods_registered",
    "ensure_ml_methods_registered",
    "ensure_network_methods_registered",
    "ensure_optimization_methods_registered",
    "ensure_policy_methods_registered",
    "ensure_sensitivity_methods_registered",
    "ensure_simulation_methods_registered",
    "ensure_spatial_methods_registered",
    "ensure_survey_methods_registered",
    "ensure_validation_methods_registered",
]
