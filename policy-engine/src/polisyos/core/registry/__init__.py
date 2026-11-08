"""Expose registry primitives and lazy bundle builders/loaders.

`BaseRegistry`/`GenericRegistry` are pure in-memory primitives imported eagerly,
while bundle construction/loading helpers are resolved lazily to avoid importing
CAS and IR schemas unless a caller explicitly needs immutable registry bundles.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .base import BaseRegistry, DuplicateDecision
from .generic import GenericRegistry, GenericRegistrySnapshot

if TYPE_CHECKING:
    from .builder import build_default_registry_bundle, build_registry_bundle
    from .builder_from_fragments import (
        FragmentPrecedencePolicy,
        build_registry_bundle_from_components,
    )
    from .loader import (
        RegistryBundleContent,
        load_registry_bundle,
        load_registry_bundle_content,
        load_registry_bundle_payload,
    )

__all__ = [
    "BaseRegistry",
    "DuplicateDecision",
    "FragmentPrecedencePolicy",
    "GenericRegistry",
    "GenericRegistrySnapshot",
    "RegistryBundleContent",
    "build_default_registry_bundle",
    "build_registry_bundle",
    "build_registry_bundle_from_components",
    "load_registry_bundle",
    "load_registry_bundle_content",
    "load_registry_bundle_payload",
]


_LAZY_IMPORTS = {
    "FragmentPrecedencePolicy": "polisyos.core.registry.builder_from_fragments",
    "RegistryBundleContent": "polisyos.core.registry.loader",
    "build_default_registry_bundle": "polisyos.core.registry.builder",
    "build_registry_bundle": "polisyos.core.registry.builder",
    "build_registry_bundle_from_components": "polisyos.core.registry.builder_from_fragments",
    "load_registry_bundle": "polisyos.core.registry.loader",
    "load_registry_bundle_content": "polisyos.core.registry.loader",
    "load_registry_bundle_payload": "polisyos.core.registry.loader",
}


def __getattr__(name: str) -> Any:
    """Resolve the exact registered owner of a public bundle helper."""
    owner = _LAZY_IMPORTS.get(name)
    if owner is None:
        raise AttributeError(f"module 'polisyos.core.registry' has no attribute {name!r}")
    return getattr(import_module(owner), name)
