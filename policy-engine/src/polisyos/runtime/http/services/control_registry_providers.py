"""Injectable registry bundle for runtime control-plane services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Iterable


class ConnectorRegistryLike(Protocol):
    """Connector registry surface required by runtime control APIs."""

    def query_entries(self, *args: Any, **kwargs: Any) -> Iterable[Any]: ...


class SourceProfileRegistryLike(Protocol):
    """Source-profile registry surface required by runtime control APIs."""

    def get(self, profile_id: str) -> Any | None: ...
    def list_all(self) -> list[Any]: ...
    def list_by_family(self, connector_family: str) -> list[Any]: ...


class BindingProfileRegistryLike(Protocol):
    """Binding-profile registry surface required by runtime control APIs."""

    def get(self, profile_id: str) -> Any | None: ...
    def list_all(self) -> list[Any]: ...


class ModelProfileRegistryLike(Protocol):
    """Model-profile registry surface required by runtime control APIs."""

    def list_all(self) -> list[Any]: ...


@dataclass(frozen=True, slots=True)
class ControlRegistryProviders:
    """Bundle registry dependencies so runtime control paths avoid singleton lookups."""

    connectors: ConnectorRegistryLike
    source_profiles: SourceProfileRegistryLike
    binding_profiles: BindingProfileRegistryLike
    model_profiles: ModelProfileRegistryLike


ConnectorRegistryFactory = Callable[[], ConnectorRegistryLike]
SourceProfileRegistryFactory = Callable[[], SourceProfileRegistryLike]
BindingProfileRegistryFactory = Callable[[], BindingProfileRegistryLike]
ModelProfileRegistryFactory = Callable[[], ModelProfileRegistryLike]


def resolve_control_registry_providers(
    *,
    connectors: ConnectorRegistryLike | None = None,
    source_profiles: SourceProfileRegistryLike | None = None,
    binding_profiles: BindingProfileRegistryLike | None = None,
    model_profiles: ModelProfileRegistryLike | None = None,
    connectors_factory: ConnectorRegistryFactory | None = None,
    source_profiles_factory: SourceProfileRegistryFactory | None = None,
    binding_profiles_factory: BindingProfileRegistryFactory | None = None,
    model_profiles_factory: ModelProfileRegistryFactory | None = None,
) -> ControlRegistryProviders:
    """Resolve runtime control registries once at the bootstrap boundary."""

    if connectors is None:
        connectors = (
            connectors_factory() if connectors_factory is not None else _default_connectors()
        )
    if source_profiles is None:
        source_profiles = (
            source_profiles_factory()
            if source_profiles_factory is not None
            else _default_source_profiles()
        )
    if binding_profiles is None:
        binding_profiles = (
            binding_profiles_factory()
            if binding_profiles_factory is not None
            else _default_binding_profiles()
        )
    if model_profiles is None:
        model_profiles = (
            model_profiles_factory()
            if model_profiles_factory is not None
            else _default_model_profiles()
        )
    return ControlRegistryProviders(
        connectors=connectors,
        source_profiles=source_profiles,
        binding_profiles=binding_profiles,
        model_profiles=model_profiles,
    )


def _default_connectors() -> ConnectorRegistryLike:
    from polisyos.fabric.connectors.registry import ConnectorRegistry

    return cast("ConnectorRegistryLike", ConnectorRegistry.get_instance())


def _default_source_profiles() -> SourceProfileRegistryLike:
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry

    return cast("SourceProfileRegistryLike", SourceProfileRegistry.get_instance())


def _default_binding_profiles() -> BindingProfileRegistryLike:
    from polisyos.fabric.connectors.bindings import BindingProfileRegistry

    return cast("BindingProfileRegistryLike", BindingProfileRegistry.get_instance())


def _default_model_profiles() -> ModelProfileRegistryLike:
    from polisyos.scientist.orchestration.llm.profiles import ModelProfileRegistry

    return cast("ModelProfileRegistryLike", ModelProfileRegistry.get_instance())


__all__ = [
    "BindingProfileRegistryLike",
    "ConnectorRegistryLike",
    "ControlRegistryProviders",
    "ModelProfileRegistryLike",
    "SourceProfileRegistryLike",
    "resolve_control_registry_providers",
]
