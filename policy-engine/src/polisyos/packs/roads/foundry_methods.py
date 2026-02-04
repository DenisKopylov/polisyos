from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata


def _create_roads_speed_cap_method() -> object:
    import numpy as np

    from polisyos.foundry.methods.base import (
        ComplexityClass,
        FidelityLevel,
        MethodMetadata,
        MethodSignature,
        SlotSpec,
        SlotType,
        Unit,
    )

    speed_unit = Unit("speed", "kmh")

    class RoadsSpeedCapMethod:
        signature = MethodSignature(
            name="speed_cap",
            namespace="roads.method",
            version="1.0.0",
            input_slots=frozenset(
                {
                    SlotSpec(
                        name="speed_input",
                        slot_type=SlotType.VECTOR,
                        unit=speed_unit,
                    )
                }
            ),
            output_slots=frozenset(
                {
                    SlotSpec(
                        name="speed_output",
                        slot_type=SlotType.VECTOR,
                        unit=speed_unit,
                    )
                }
            ),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_N,
        )
        metadata = MethodMetadata(
            description="Clamp agent speed by configured cap.",
            tags=frozenset({"roads", "safety"}),
        )

        @staticmethod
        def pure_step(state, params):
            cap = float(params.get("cap", 50.0))
            values = np.asarray(state)
            return np.minimum(values, cap)

    return RoadsSpeedCapMethod


@dataclass(frozen=True)
class _StaticComponent:
    metadata: ComponentMetadata
    factory: Callable[[], object]

    def create(self) -> object:
        return self.factory()


roads_method_component = _StaticComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("roads.method.speed_cap@1.0.0"),
        kind=ComponentKind.FOUNDRY_METHOD,
        abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
        domains=["roads"],
        jurisdictions=[],
        tags=["pack:roads", "foundry"],
        capabilities=Capability.FOUNDRY_METHOD | Capability.FOUNDRY_COMPILE,
        deps=[],
        display_name="Roads Speed Cap Method",
        description="Simple Foundry method component for roads domain.",
    ),
    factory=_create_roads_speed_cap_method,
)


__all__ = ["roads_method_component"]
