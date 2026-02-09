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
from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.components_bridge import bootstrap_method_registry_from_components
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.resolution import ResolutionPolicy


class _RoadsMethod:
    signature = MethodSignature(
        name="bridge_method",
        namespace="roads.method",
        version="1.0.0",
        input_slots=frozenset(
            {SlotSpec(name="x", slot_type=SlotType.SCALAR, unit=Unit("none", "1"))}
        ),
        output_slots=frozenset(
            {SlotSpec(name="y", slot_type=SlotType.SCALAR, unit=Unit("none", "1"))}
        ),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )
    metadata = MethodMetadata(description="bridge test", tags=frozenset({"native"}))

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
        return state


@dataclass(frozen=True)
class _MethodComponent:
    metadata: ComponentMetadata

    def create(self):
        return _RoadsMethod


def test_foundry_method_discovery_and_selection() -> None:
    MethodRegistry.reset_instance()
    registry = MethodRegistry.get_instance()

    metadata = ComponentMetadata(
        component_id=ComponentId.parse("roads.method.bridge_method@1.0.0"),
        kind=ComponentKind.FOUNDRY_METHOD,
        abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
        domains=["roads"],
        jurisdictions=[],
        tags=["transport"],
        capabilities=Capability.FOUNDRY_METHOD,
        deps=[],
    )

    component_registry = ComponentRegistry()
    component_registry.register(
        ComponentEntry(
            metadata=metadata,
            component=_MethodComponent(metadata=metadata),
            source=DiscoverySourceInfo(source_type="entry_point", location="test"),
        )
    )

    report = bootstrap_method_registry_from_components(
        component_registry,
        registry,
        resolution_policy=ResolutionPolicy.LATEST,
    )

    assert report.errors == []
    assert report.registered == ["roads.method.bridge_method@1.0.0"]

    selected = registry.get("roads.method.bridge_method", policy=ResolutionPolicy.LATEST)
    assert selected.signature.fqn == "roads.method.bridge_method@1.0.0"

    by_domain_tag = list(registry.query(tags={"domain:roads"}))
    assert [sig.fqn for sig in by_domain_tag] == ["roads.method.bridge_method@1.0.0"]

    MethodRegistry.reset_instance()
