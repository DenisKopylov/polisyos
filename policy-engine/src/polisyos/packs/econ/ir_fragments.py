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


def _build_econ_fragment() -> UnitsFragment:
    return UnitsFragment(
        meta=RegistryFragmentMeta(
            fragment_id="econ.fragment.units",
            namespace="roads",
            priority=90,
            notes=["Conflicting roads units fragment for precedence tests"],
        ),
        payload=UnitsRegistry(
            units={
                "roads.kmh": GenericUnit(
                    label="kmh",
                    description="Alternative roads speed unit from econ pack",
                ),
            }
        ),
    )


econ_ir_fragment_component = _StaticComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("econ.ir.registry_fragment@1.0.0"),
        kind=ComponentKind.IR_FRAGMENT,
        abi_targets={"ir_abi": "1.x"},
        domains=["roads"],
        jurisdictions=[],
        tags=["pack:econ", "ir", "conflict_demo"],
        capabilities=Capability.IR_FRAGMENT,
        deps=[],
        display_name="Econ IR Fragment",
        description="Conflict-demo fragment overriding roads units.",
    ),
    factory=_build_econ_fragment,
)


__all__ = ["econ_ir_fragment_component"]
