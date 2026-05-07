"""Public authoring contract for Foundry method extensions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
)
from polisyos.foundry.methods.base import FoundryMethod, MethodMetadata, MethodSignature

FOUNDRY_METHODS_API_VERSION = "3.5.0"
FOUNDRY_METHODS_API_RANGE = ">=3.5.0,<4.0.0"


@runtime_checkable
class FoundryMethodPlugin(Protocol):
    """Component-style plugin that creates one Foundry method class."""

    @property
    def metadata(self) -> ComponentMetadata: ...

    def create(self) -> type[FoundryMethod]: ...


@dataclass(frozen=True, slots=True)
class FoundryMethodComponent:
    """Concrete plugin object for a single Foundry method class."""

    method_class: type[FoundryMethod]
    metadata: ComponentMetadata

    def create(self) -> type[FoundryMethod]:
        """Return the method class consumed by the registry bridge."""
        return self.method_class


def component_for_method(
    method_class: type[FoundryMethod],
    *,
    domains: list[str] | tuple[str, ...] | None = None,
    tags: list[str] | tuple[str, ...] | set[str] | frozenset[str] | None = None,
    abi_targets: dict[str, str] | None = None,
    display_name: str | None = None,
    description: str | None = None,
) -> FoundryMethodComponent:
    """Build a `FoundryMethodPlugin` for an existing method class."""
    return FoundryMethodComponent(
        method_class=method_class,
        metadata=metadata_for_method(
            method_class,
            domains=domains,
            tags=tags,
            abi_targets=abi_targets,
            display_name=display_name,
            description=description,
        ),
    )


def metadata_for_method(
    method_class: type[FoundryMethod],
    *,
    domains: list[str] | tuple[str, ...] | None = None,
    tags: list[str] | tuple[str, ...] | set[str] | frozenset[str] | None = None,
    abi_targets: dict[str, str] | None = None,
    display_name: str | None = None,
    description: str | None = None,
) -> ComponentMetadata:
    """Derive component metadata from a `FoundryMethod` signature and metadata."""
    signature, method_metadata = _method_contract(method_class)
    tag_set = {str(tag) for tag in method_metadata.tags}
    tag_set.update(str(tag) for tag in tags or ())

    return ComponentMetadata(
        component_id=ComponentId.parse(signature.fqn),
        kind=ComponentKind.FOUNDRY_METHOD,
        abi_targets=abi_targets or {"foundry_methods_api": FOUNDRY_METHODS_API_RANGE},
        domains=list(domains) if domains is not None else _domains_for_signature(signature),
        jurisdictions=[],
        tags=sorted(tag_set),
        capabilities=Capability.FOUNDRY_METHOD,
        deps=[],
        display_name=display_name or method_class.__name__,
        description=description or method_metadata.description,
        provides=[signature.fqn],
    )


def _method_contract(
    method_class: type[FoundryMethod],
) -> tuple[MethodSignature, MethodMetadata]:
    if not isinstance(method_class, type):
        raise TypeError("Foundry method plugin must wrap a class")

    signature = getattr(method_class, "signature", None)
    if not isinstance(signature, MethodSignature):
        raise TypeError("Foundry method class must define MethodSignature as `signature`")

    metadata = getattr(method_class, "metadata", None)
    if not isinstance(metadata, MethodMetadata):
        raise TypeError("Foundry method class must define MethodMetadata as `metadata`")

    if not hasattr(method_class, "pure_step"):
        raise TypeError("Foundry method class must define static `pure_step`")

    return signature, metadata


def _domains_for_signature(signature: MethodSignature) -> list[str]:
    domains = [signature.namespace.split(".", 1)[0]]
    family_root = str(signature.family or "").split(".", 1)[0]
    if family_root and family_root not in domains:
        domains.append(family_root)
    return domains


__all__ = [
    "FOUNDRY_METHODS_API_RANGE",
    "FOUNDRY_METHODS_API_VERSION",
    "FoundryMethodComponent",
    "FoundryMethodPlugin",
    "component_for_method",
    "metadata_for_method",
]
