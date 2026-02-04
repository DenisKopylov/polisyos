from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.kernel.units import GenericUnit, UnitsRegistry
from polisyos.ir.registry_fragments import RegistryFragmentMeta, UnitsFragment


@dataclass(frozen=True)
class _StaticComponent:
    metadata: ComponentMetadata
    factory: Callable[[], object]

    def create(self) -> object:
        return self.factory()


def _build_roads_fragment() -> UnitsFragment:
    return UnitsFragment(
        meta=RegistryFragmentMeta(
            fragment_id="roads.fragment.units",
            namespace="roads",
            priority=100,
            notes=["Built-in roads units fragment"],
        ),
        payload=UnitsRegistry(
            units={
                "roads.kmh": GenericUnit(
                    label="kmh",
                    description="Road speed in kilometers per hour",
                ),
            }
        ),
    )


roads_ir_fragment_component = _StaticComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("roads.ir.registry_fragment@1.0.0"),
        kind=ComponentKind.IR_FRAGMENT,
        abi_targets={"ir_abi": "1.x"},
        domains=["roads"],
        jurisdictions=[],
        tags=["pack:roads", "ir"],
        capabilities=Capability.IR_FRAGMENT,
        provides=["ir.registry.units"],
        deps=[],
        display_name="Roads IR Fragment",
        description="Adds roads-specific IR registry units.",
    ),
    factory=_build_roads_fragment,
)


__all__ = ["roads_ir_fragment_component"]
