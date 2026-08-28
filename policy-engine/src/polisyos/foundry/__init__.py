"""Expose the stable Foundry compile/execute entrypoints behind lazy imports.

`polisyos.foundry` is the user-facing facade for turning Trinity bundles into
`ExecPlan` artifacts and replaying those plans against bound `GlobalState`
snapshots. Exports stay lazy so CLI/docs imports do not eagerly load JAX,
solver, or optional catalog backends unless `compile()` or `execute()` is
actually called.

The stable public surface of this package is intentionally narrow.  Alongside
compile/execute and W7 method selection, it exposes three generic text-embedding
surfaces plus the Foundry-owned N8 dependency-authority request, its
negative-only result union, and the two catalog boundaries that resolve that
authority before reading candidate runtime posture.
"""

from __future__ import annotations

import importlib
import sys
import threading
import types
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.foundry.methods.backends.protocol import (
        EmbedderProtocol,
        SentenceTransformerEmbedder,
        TFIDFEmbedder,
    )

__all__ = [
    "DependencyProfileResolutionFailure",
    "EmbedderProtocol",
    "MethodCatalogDependencyAuthorityRequest",
    "SentenceTransformerEmbedder",
    "TFIDFEmbedder",
    "build_method_catalog_provenance_manifest",
    "build_method_catalog_runtime_identity",
    "compile",
    "compile_program",
    "execute",
    "select_method_candidates_for_requirements",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DependencyProfileResolutionFailure": (
        "polisyos.foundry.methods.catalog.dependency_authority",
        "DependencyProfileResolutionFailure",
    ),
    "EmbedderProtocol": (
        "polisyos.foundry.methods.backends.protocol",
        "EmbedderProtocol",
    ),
    "MethodCatalogDependencyAuthorityRequest": (
        "polisyos.foundry.methods.catalog.dependency_authority",
        "MethodCatalogDependencyAuthorityRequest",
    ),
    "SentenceTransformerEmbedder": (
        "polisyos.foundry.methods.backends.protocol",
        "SentenceTransformerEmbedder",
    ),
    "TFIDFEmbedder": (
        "polisyos.foundry.methods.backends.protocol",
        "TFIDFEmbedder",
    ),
    "build_method_catalog_provenance_manifest": (
        "polisyos.foundry.methods.catalog.snapshot",
        "build_method_catalog_provenance_manifest",
    ),
    "build_method_catalog_runtime_identity": (
        "polisyos.foundry.methods.catalog.snapshot",
        "build_method_catalog_runtime_identity",
    ),
    "compile": ("polisyos.foundry.api", "compile"),
    "compile_program": ("polisyos.foundry.api", "compile_program"),
    "execute": ("polisyos.foundry.api", "execute"),
    "select_method_candidates_for_requirements": (
        "polisyos.foundry.methods.selection",
        "select_method_candidates_for_requirements",
    ),
}
_RESOLVED_EXPORTS: dict[str, object] = {}
_RESOLVE_LOCK = threading.Lock()


def _resolve_lazy_export(name: str) -> object:
    """Resolve and memoize one stable facade export."""
    with _RESOLVE_LOCK:
        cached = _RESOLVED_EXPORTS.get(name)
        if cached is not None:
            return cached
        module_name, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr_name)
        _RESOLVED_EXPORTS[name] = value
        return value


def __getattr__(name: str) -> object:
    """Resolve a lazy public export on first access.

    Args:
        name: Export name requested from the package facade.

    Returns:
        The resolved function object, memoized in module globals.

    Raises:
        AttributeError: If `name` is neither part of the stable Foundry facade
            nor a real Foundry submodule.
    """
    if name in _LAZY_IMPORTS:
        return _resolve_lazy_export(name)

    module_name = f"{__name__}.{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise AttributeError(f"module 'polisyos.foundry' has no attribute '{name}'") from None
        raise
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    """Return eager globals plus lazy facade exports for interactive discovery."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))


class _FoundryFacadeModule(types.ModuleType):
    """
    Keep package-level exports stable even when submodule imports shadow names.

    The facade no longer mutates root module globals on first access; instead
    it resolves through a locked side cache and only intercepts attribute reads
    when a lazy export name has been shadowed by a submodule object.
    """

    def __getattribute__(self, name: str) -> object:
        lazy_imports = types.ModuleType.__getattribute__(self, "_LAZY_IMPORTS")
        if name in lazy_imports:
            module_dict = types.ModuleType.__getattribute__(self, "__dict__")
            current = module_dict.get(name)
            if current is None:
                return _resolve_lazy_export(name)
        return types.ModuleType.__getattribute__(self, name)


sys.modules[__name__].__class__ = _FoundryFacadeModule
