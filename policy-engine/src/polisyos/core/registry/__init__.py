from __future__ import annotations

from typing import Any

from .base import BaseRegistry, DuplicateDecision
from .generic import GenericRegistry, GenericRegistrySnapshot

__all__ = [
    "BaseRegistry",
    "DuplicateDecision",
    "RegistryBundleContent",
    "FragmentPrecedencePolicy",
    "build_default_registry_bundle",
    "build_registry_bundle_from_components",
    "build_registry_bundle",
    "GenericRegistry",
    "GenericRegistrySnapshot",
    "load_registry_bundle",
    "load_registry_bundle_content",
    "load_registry_bundle_payload",
]


def __getattr__(name: str) -> Any:
    if name in {
        "RegistryBundleContent",
        "load_registry_bundle",
        "load_registry_bundle_content",
        "load_registry_bundle_payload",
    }:
        from . import loader as _loader

        return getattr(_loader, name)
    if name in {"build_default_registry_bundle", "build_registry_bundle"}:
        from . import builder as _builder

        return getattr(_builder, name)
    if name in {"FragmentPrecedencePolicy", "build_registry_bundle_from_components"}:
        from . import builder_from_fragments as _fragments

        return getattr(_fragments, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
