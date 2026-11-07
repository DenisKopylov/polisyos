"""Expose registry primitives and lazy bundle builders/loaders.

`BaseRegistry`/`GenericRegistry` are pure in-memory primitives imported eagerly,
while bundle construction/loading helpers are resolved lazily to avoid importing
CAS and IR schemas unless a caller explicitly needs immutable registry bundles.
"""

from __future__ import annotations

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


def __getattr__(name: str) -> Any:
    """Resolve one lazily exported bundle helper from `builder`, `loader`, or fragment builders."""
    if name in {
        "RegistryBundleContent",
        "load_registry_bundle",
        "load_registry_bundle_content",
        "load_registry_bundle_payload",
    }:
        from .loader import (
            RegistryBundleContent,
            load_registry_bundle,
            load_registry_bundle_content,
            load_registry_bundle_payload,
        )

        providers = {
            "RegistryBundleContent": RegistryBundleContent,
            "load_registry_bundle": load_registry_bundle,
            "load_registry_bundle_content": load_registry_bundle_content,
            "load_registry_bundle_payload": load_registry_bundle_payload,
        }
        return providers[name]
    if name in {"build_default_registry_bundle", "build_registry_bundle"}:
        from .builder import build_default_registry_bundle, build_registry_bundle

        providers = {
            "build_default_registry_bundle": build_default_registry_bundle,
            "build_registry_bundle": build_registry_bundle,
        }
        return providers[name]
    if name in {"FragmentPrecedencePolicy", "build_registry_bundle_from_components"}:
        from .builder_from_fragments import (
            FragmentPrecedencePolicy,
            build_registry_bundle_from_components,
        )

        providers = {
            "FragmentPrecedencePolicy": FragmentPrecedencePolicy,
            "build_registry_bundle_from_components": build_registry_bundle_from_components,
        }
        return providers[name]
    raise AttributeError(f"module 'polisyos.core.registry' has no attribute {name!r}")
