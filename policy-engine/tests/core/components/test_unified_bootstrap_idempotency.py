from __future__ import annotations

from polisyos.core.components import ComponentEntry, ComponentRegistry, bootstrap_plugin_registries
from polisyos.core.components.discovery import DiscoverySourceInfo
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.packs.roads.foundry_methods import roads_method_component


def test_unified_bootstrap_is_idempotent_for_methods() -> None:
    MethodRegistry.reset_instance()

    index = ComponentRegistry()
    index.register(
        ComponentEntry(
            metadata=roads_method_component.metadata,
            component=roads_method_component,
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
    assert methods_first.registered == ["roads.method.speed_cap@1.0.0"]

    assert methods_second.errors == []
    assert methods_second.registered == []
    assert methods_second.duplicates == ["roads.method.speed_cap@1.0.0"]

    MethodRegistry.reset_instance()
