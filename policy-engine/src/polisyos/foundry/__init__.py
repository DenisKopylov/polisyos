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
Candidate method route constraints and their input-contract relation predicate
also cross this stable facade; their implementation stays with method selection.
Legal subject recognition exposes independently addressed source comparisons;
these candidate results do not confer legal authority.
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
    from polisyos.foundry.methods.selection import (
        MethodRouteConstraint,
        method_accepts_input_contract,
    )
    from polisyos.foundry.validation.legal_correspondence import (
        LegalCorrespondenceRequest,
        LegalCorrespondenceResult,
        LegalSubjectAnnotationSource,
        LegalSubjectIdentity,
        LegalSubjectMembership,
        LegalSubjectMembershipSource,
        bind_legal_subject_annotations,
        persist_legal_correspondence_result,
        persist_legal_subject_annotations,
        persist_legal_subject_membership_source,
        produce_legal_subject_spine,
        recognize_legal_correspondence,
    )

__all__ = [
    "DependencyProfileResolutionFailure",
    "EmbedderProtocol",
    "LegalCorrespondenceRequest",
    "LegalCorrespondenceResult",
    "LegalSubjectAnnotationSource",
    "LegalSubjectIdentity",
    "LegalSubjectMembership",
    "LegalSubjectMembershipSource",
    "MethodCatalogDependencyAuthorityRequest",
    "MethodRouteConstraint",
    "SentenceTransformerEmbedder",
    "TFIDFEmbedder",
    "bind_legal_subject_annotations",
    "build_method_catalog_provenance_manifest",
    "build_method_catalog_runtime_identity",
    "compile",
    "compile_program",
    "execute",
    "method_accepts_input_contract",
    "persist_legal_correspondence_result",
    "persist_legal_subject_annotations",
    "persist_legal_subject_membership_source",
    "produce_legal_subject_spine",
    "recognize_legal_correspondence",
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
    "LegalCorrespondenceRequest": (
        "polisyos.foundry.validation.legal_correspondence",
        "LegalCorrespondenceRequest",
    ),
    "LegalCorrespondenceResult": (
        "polisyos.foundry.validation.legal_correspondence",
        "LegalCorrespondenceResult",
    ),
    "LegalSubjectAnnotationSource": (
        "polisyos.foundry.validation.legal_correspondence",
        "LegalSubjectAnnotationSource",
    ),
    "LegalSubjectIdentity": (
        "polisyos.foundry.validation.legal_correspondence",
        "LegalSubjectIdentity",
    ),
    "LegalSubjectMembership": (
        "polisyos.foundry.validation.legal_correspondence",
        "LegalSubjectMembership",
    ),
    "LegalSubjectMembershipSource": (
        "polisyos.foundry.validation.legal_correspondence",
        "LegalSubjectMembershipSource",
    ),
    "MethodCatalogDependencyAuthorityRequest": (
        "polisyos.foundry.methods.catalog.dependency_authority",
        "MethodCatalogDependencyAuthorityRequest",
    ),
    "MethodRouteConstraint": (
        "polisyos.foundry.methods.selection",
        "MethodRouteConstraint",
    ),
    "SentenceTransformerEmbedder": (
        "polisyos.foundry.methods.backends.protocol",
        "SentenceTransformerEmbedder",
    ),
    "TFIDFEmbedder": (
        "polisyos.foundry.methods.backends.protocol",
        "TFIDFEmbedder",
    ),
    "bind_legal_subject_annotations": (
        "polisyos.foundry.validation.legal_correspondence",
        "bind_legal_subject_annotations",
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
    "method_accepts_input_contract": (
        "polisyos.foundry.methods.selection",
        "method_accepts_input_contract",
    ),
    "persist_legal_correspondence_result": (
        "polisyos.foundry.validation.legal_correspondence",
        "persist_legal_correspondence_result",
    ),
    "persist_legal_subject_annotations": (
        "polisyos.foundry.validation.legal_correspondence",
        "persist_legal_subject_annotations",
    ),
    "persist_legal_subject_membership_source": (
        "polisyos.foundry.validation.legal_correspondence",
        "persist_legal_subject_membership_source",
    ),
    "produce_legal_subject_spine": (
        "polisyos.foundry.validation.legal_correspondence",
        "produce_legal_subject_spine",
    ),
    "recognize_legal_correspondence": (
        "polisyos.foundry.validation.legal_correspondence",
        "recognize_legal_correspondence",
    ),
    "select_method_candidates_for_requirements": (
        "polisyos.foundry.methods.selection",
        "select_method_candidates_for_requirements",
    ),
}
_RESOLVED_EXPORTS: dict[str, object] = {}
# An exported module can import another export from this same facade.
_RESOLVE_LOCK = threading.RLock()


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
