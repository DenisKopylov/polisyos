"""Small real registered methods shared by native chain qualification tests."""

from __future__ import annotations

from typing import Any, ClassVar

from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)


def slot(name: str, contract: str | None = None) -> SlotSpec:
    return SlotSpec(
        name=name,
        slot_type=SlotType.SCALAR,
        unit=Unit(dimension="native_chain", symbol="unit"),
        contract_id=contract,
    )


def signature(name: str, *, inputs=(), outputs=(), parameters=(), requires=()) -> MethodSignature:
    return MethodSignature(
        name=name,
        namespace="tests.native_chain",
        version="1.0.0",
        input_slots=frozenset(inputs),
        output_slots=frozenset(outputs),
        parameters=tuple(parameters),
        requires=frozenset(requires),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


class Required:
    signature: ClassVar[MethodSignature] = signature("required", outputs=(slot("value"),))
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Add five to the declared sentinel."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"value": state["sentinel"] + 5}


class Dependent:
    signature: ClassVar[MethodSignature] = signature(
        "dependent", outputs=(slot("answer"),), requires=(Required.signature.fqn,)
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Consume the committed prerequisite."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"answer": 3 * state["value"]}


class Independent:
    signature: ClassVar[MethodSignature] = signature("independent", outputs=(slot("independent"),))
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Supply an independent sibling result."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"independent": 9}


class ParameterEcho:
    signature: ClassVar[MethodSignature] = signature(
        "parameter_echo",
        outputs=(slot("answer"),),
        parameters=(
            ParameterSpec(name="window", default=7, is_static=True),
            ParameterSpec(name="scale", default=2, is_static=False),
        ),
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Multiply authored window and scale."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"answer": params["window"] * params["scale"]}


class Left:
    signature: ClassVar[MethodSignature] = signature("left", outputs=(slot("left"),))
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Supply the first declared value."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"left": 10}


class Right:
    signature: ClassVar[MethodSignature] = signature("right", outputs=(slot("right"),))
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Supply the second declared value."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"right": 20}


class Merge:
    signature: ClassVar[MethodSignature] = signature(
        "merge", inputs=(slot("left"), slot("right")), outputs=(slot("merged"),)
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Own the explicit sum operation."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"merged": state["left"] + state["right"]}


class Twice:
    signature: ClassVar[MethodSignature] = signature(
        "twice", inputs=(slot("merged"),), outputs=(slot("answer"),)
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Double the explicitly merged value."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"answer": 2 * state}


class Flexible:
    signature: ClassVar[MethodSignature] = signature(
        "flexible", outputs=(slot("a_flexible"), slot("b_fixed", "B"))
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Expose flexible and fixed source slots."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"a_flexible": 10, "b_fixed": 20}


class Matched:
    signature: ClassVar[MethodSignature] = signature(
        "matched", inputs=(slot("c_first", "B"), slot("d_second", "A")), outputs=(slot("answer"),)
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Distinguish the two selected source bindings."
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {"answer": 100 * state["c_first"] + state["d_second"]}


METHODS = (
    Required,
    Dependent,
    Independent,
    ParameterEcho,
    Left,
    Right,
    Merge,
    Twice,
    Flexible,
    Matched,
)


def register_methods():
    from polisyos.foundry.methods.registry import MethodRegistry

    registry = MethodRegistry.get_instance()
    for method in METHODS:
        registry.register(method, override=True)
    return registry
