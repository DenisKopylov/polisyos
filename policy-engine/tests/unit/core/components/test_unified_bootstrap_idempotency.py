from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from polisyos.core.components import (
    Capability,
    ComponentEntry,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
    ComponentRegistry,
    bootstrap_plugin_registries,
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
from polisyos.foundry.methods.registry import MethodRegistry


def _create_stub_method() -> type:
    stub_unit = Unit("test", "unit")

    class StubMethod:
        signature = MethodSignature(
            name="stub",
            namespace="test.method",
            version="1.0.0",
            input_slots=frozenset({SlotSpec(name="in", slot_type=SlotType.SCALAR, unit=stub_unit)}),
            output_slots=frozenset(
                {SlotSpec(name="out", slot_type=SlotType.SCALAR, unit=stub_unit)}
            ),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_1,
        )
        metadata = MethodMetadata(
            description="Stub method for idempotency test.",
            tags=frozenset({"test"}),
        )

        @staticmethod
        def pure_step(state, params):
            return state

    return StubMethod


@dataclass(frozen=True)
class _StubComponent:
    metadata: ComponentMetadata
    factory: Callable[[], object]

    def create(self) -> object:
        return self.factory()


_stub_method_component = _StubComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("test.method.stub@1.0.0"),
        kind=ComponentKind.FOUNDRY_METHOD,
        abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
        domains=["test"],
        jurisdictions=[],
        tags=["test"],
        capabilities=Capability.FOUNDRY_METHOD | Capability.FOUNDRY_COMPILE,
        deps=[],
        display_name="Test Stub Method",
        description="Inline stub for bootstrap idempotency test.",
    ),
    factory=_create_stub_method,
)


def test_unified_bootstrap_is_idempotent_for_methods() -> None:
    MethodRegistry.reset_instance()

    index = ComponentRegistry()
    index.register(
        ComponentEntry(
            metadata=_stub_method_component.metadata,
            component=_stub_method_component,
            source=DiscoverySourceInfo(source_type="entry_point", location="tests"),
        )
    )

    first = bootstrap_plugin_registries(
        index,
        bootstrap_connectors=False,
        bootstrap_methods=True,
        bootstrap_evaluators=False,
        bootstrap_extractors=False,
        bootstrap_providers=False,
        bootstrap_nodes=False,
    )
    second = bootstrap_plugin_registries(
        index,
        bootstrap_connectors=False,
        bootstrap_methods=True,
        bootstrap_evaluators=False,
        bootstrap_extractors=False,
        bootstrap_providers=False,
        bootstrap_nodes=False,
    )

    methods_first = first.domains["methods"]
    methods_second = second.domains["methods"]

    assert methods_first.errors == []
    assert methods_first.registered == ["test.method.stub@1.0.0"]

    assert methods_second.errors == []
    assert methods_second.registered == []
    assert methods_second.duplicates == ["test.method.stub@1.0.0"]

    MethodRegistry.reset_instance()
