from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from polisyos.core.components import (
    Capability,
    ComponentEntry,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
    ComponentRegistry,
)
from polisyos.core.components.discovery import DiscoverySourceInfo
from polisyos.foundry.methods.components_bridge import bootstrap_method_registry_from_components
from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.registry import MethodRegistry


def _legacy_method_class() -> type:
    unit = Unit("none", "1")

    class LegacyMethod:
        signature = MethodSignature(
            name="sample",
            namespace="legacy.group",
            version="1.0.0",
            input_slots=frozenset({SlotSpec("x", SlotType.SCALAR, unit)}),
            output_slots=frozenset({SlotSpec("y", SlotType.SCALAR, unit)}),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_1,
        )
        metadata = MethodMetadata(
            description="legacy test method",
            tags=frozenset({"legacy"}),
        )

        @staticmethod
        def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
            del params
            return state

    return LegacyMethod


@dataclass(frozen=True)
class _LegacyMethodComponent:
    metadata: ComponentMetadata
    method_class: type

    def create(self) -> type:
        return self.method_class


def test_components_bridge_registers_methods_without_legacy_bootstrap_adapter() -> None:
    MethodRegistry.reset_instance()
    registry = MethodRegistry.get_instance()

    method_class = _legacy_method_class()
    metadata = ComponentMetadata(
        component_id=ComponentId.parse("legacy.group.sample@1.0.0"),
        kind=ComponentKind.FOUNDRY_METHOD,
        abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
        domains=["legacy"],
        jurisdictions=[],
        tags=["legacy"],
        capabilities=Capability.FOUNDRY_METHOD,
        deps=[],
        description="legacy test method",
        display_name="LegacyMethod",
    )

    component_registry = ComponentRegistry()
    component_registry.register(
        ComponentEntry(
            metadata=metadata,
            component=_LegacyMethodComponent(metadata=metadata, method_class=method_class),
            source=DiscoverySourceInfo(source_type="entry_point", location="test"),
        )
    )

    report = bootstrap_method_registry_from_components(component_registry, registry)

    assert report.errors == []
    assert report.registered == ["legacy.group.sample@1.0.0"]

    resolved = registry.get("legacy.group.sample@1.0.0")
    assert resolved.signature.fqn == "legacy.group.sample@1.0.0"

    MethodRegistry.reset_instance()
