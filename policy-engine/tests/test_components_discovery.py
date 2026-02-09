from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.components.discovery import (
    ENTRY_POINT_GROUP_FOUNDRY_METHODS,
    ENTRY_POINT_GROUP_IR_FRAGMENTS,
    discover_components,
)


@dataclass(frozen=True)
class _TestComponent:
    metadata: ComponentMetadata

    def create(self) -> object:
        return object()


class _FakeEntryPoint:
    def __init__(self, *, group: str, name: str, loader):
        self.group = group
        self.name = name
        self._loader = loader
        self.value = f"{name}:factory"
        self.module = name
        self.attr = "factory"

    def load(self):
        return self._loader


class _FakeEntryPoints:
    def __init__(self, by_group: dict[str, list[_FakeEntryPoint]]) -> None:
        self._by_group = by_group

    def select(self, *, group: str):
        return list(self._by_group.get(group, []))


def test_discovery_entry_points_loads_components(monkeypatch) -> None:
    ir_component = _TestComponent(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("roads.ir.test_fragment@1.0.0"),
            kind=ComponentKind.IR_FRAGMENT,
            abi_targets={"ir_abi": "1.x"},
            domains=["roads"],
            jurisdictions=[],
            tags=[],
            capabilities=Capability.IR_FRAGMENT,
            deps=[],
        )
    )
    method_component = _TestComponent(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("roads.method.demo@1.0.0"),
            kind=ComponentKind.FOUNDRY_METHOD,
            abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
            domains=["roads"],
            jurisdictions=[],
            tags=[],
            capabilities=Capability.FOUNDRY_METHOD,
            deps=[],
        )
    )

    entry_points = _FakeEntryPoints(
        {
            ENTRY_POINT_GROUP_IR_FRAGMENTS: [
                _FakeEntryPoint(
                    group=ENTRY_POINT_GROUP_IR_FRAGMENTS,
                    name="roads.ir",
                    loader=lambda: ir_component,
                ),
            ],
            ENTRY_POINT_GROUP_FOUNDRY_METHODS: [
                _FakeEntryPoint(
                    group=ENTRY_POINT_GROUP_FOUNDRY_METHODS,
                    name="roads.method",
                    loader=lambda: method_component,
                ),
            ],
        }
    )

    monkeypatch.setattr(
        "polisyos.core.components.discovery.metadata.entry_points",
        lambda: entry_points,
    )

    report = discover_components(
        groups=[ENTRY_POINT_GROUP_IR_FRAGMENTS, ENTRY_POINT_GROUP_FOUNDRY_METHODS],
        include_dev_scan=False,
    )

    ids = {str(item.metadata.component_id) for item in report.components}
    assert "roads.ir.test_fragment@1.0.0" in ids
    assert "roads.method.demo@1.0.0" in ids
    assert report.sources_processed == 2
    assert report.errors == []
    assert all(item.source.source_type == "entry_point" for item in report.components)
