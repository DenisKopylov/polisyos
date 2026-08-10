"""Canonical Foundry extension discovery and registry facade."""

from .api import (
    FOUNDRY_METHODS_API_RANGE,
    FOUNDRY_METHODS_API_VERSION,
    FoundryMethodComponent,
    FoundryMethodPlugin,
    component_for_method,
    metadata_for_method,
)

_LAZY_IMPORTS = {
    "ENTRY_POINT_GROUP": ("polisyos.foundry.extensions.discovery", "ENTRY_POINT_GROUP"),
    "FoundryExtensionRegistryReport": (
        "polisyos.foundry.extensions.registry",
        "FoundryExtensionRegistryReport",
    ),
    "MethodRegistry": ("polisyos.foundry.extensions.registry", "MethodRegistry"),
    "UnboundFoundryDiscoveryInputError": (
        "polisyos.foundry.extensions.registry",
        "UnboundFoundryDiscoveryInputError",
    ),
    "bootstrap_foundry_method_registry": (
        "polisyos.foundry.extensions.registry",
        "bootstrap_foundry_method_registry",
    ),
    "bootstrap_builtin_foundry_method_family": (
        "polisyos.foundry.extensions.registry",
        "bootstrap_builtin_foundry_method_family",
    ),
    "controlled_builtin_foundry_method_registry_scope": (
        "polisyos.foundry.extensions.registry",
        "controlled_builtin_foundry_method_registry_scope",
    ),
    "build_foundry_method_components_index": (
        "polisyos.foundry.extensions.discovery",
        "build_foundry_method_components_index",
    ),
    "discover_foundry_method_components": (
        "polisyos.foundry.extensions.discovery",
        "discover_foundry_method_components",
    ),
    "get_registry": ("polisyos.foundry.extensions.registry", "get_registry"),
    "register_foundry_method_plugin": (
        "polisyos.foundry.extensions.registry",
        "register_foundry_method_plugin",
    ),
    "registry_scope": ("polisyos.foundry.extensions.registry", "registry_scope"),
}


def __getattr__(name: str) -> object:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.extensions' has no attribute {name!r}")
    import importlib

    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals()) + list(_LAZY_IMPORTS))


__all__ = [
    "ENTRY_POINT_GROUP",
    "FOUNDRY_METHODS_API_RANGE",
    "FOUNDRY_METHODS_API_VERSION",
    "FoundryExtensionRegistryReport",
    "FoundryMethodComponent",
    "FoundryMethodPlugin",
    "MethodRegistry",
    "UnboundFoundryDiscoveryInputError",
    "bootstrap_builtin_foundry_method_family",
    "bootstrap_foundry_method_registry",
    "controlled_builtin_foundry_method_registry_scope",
    "build_foundry_method_components_index",
    "component_for_method",
    "discover_foundry_method_components",
    "get_registry",
    "metadata_for_method",
    "register_foundry_method_plugin",
    "registry_scope",
]
