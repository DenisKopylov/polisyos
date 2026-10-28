"""Behavioral witnesses for the fusion lookup guard and its normal path."""

from __future__ import annotations

from typing import Any, ClassVar

import jax.numpy as jnp
import pytest

import polisyos.foundry.methods.backends.chain_executor as executor
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.components.composer import MethodComposer
from polisyos.foundry.methods.selection.registry import MethodRegistry

_SIGNAL = SlotSpec(name="signal", slot_type=SlotType.SCALAR, unit=Unit("none", "1"))


class _Producer:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="emit",
        namespace="tests.c60_fusion",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset({_SIGNAL}),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.JAX,
        supports_jit=True,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="C60 fusion producer")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> Any:
        return state + 1.0


class _Consumer:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="consume",
        namespace="tests.c60_fusion",
        version="1.0.0",
        input_slots=frozenset({_SIGNAL}),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.JAX,
        supports_jit=True,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="C60 fusion consumer")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> Any:
        return state * 3.0


@pytest.mark.parametrize("lookup", ("available", "missing_once", "raises_once"))
def test_fusion_uses_real_pair_or_falls_back_on_failed_lookup(lookup: str, monkeypatch) -> None:
    """An unavailable second class never enters fusion and still executes sequentially."""
    registry = MethodRegistry._create_fresh()
    registry.register(_Producer)
    registry.register(_Consumer)
    composer = MethodComposer(registry=registry)
    first = composer.add(_Producer.signature.fqn)
    second = composer.add(_Consumer.signature.fqn)
    composer.connect(first, second, {"signal": "signal"})
    chain = composer.build()
    assert executor._can_fuse_pair(chain, first.id, second.id)

    # An empty cache makes the actual pair builder observable in each case.
    monkeypatch.setattr(executor, "_FUSED_JIT_CACHE", executor._FusedJitCache())
    built = []
    produced = []
    real_build = executor._compile_fused_pair_kernel
    real_result = executor._build_fused_result

    def capture_build(*args, **kwargs):
        built.append((args[0], args[1]))
        return real_build(*args, **kwargs)

    def capture_result(*args, **kwargs):
        result = real_result(*args, **kwargs)
        produced.append(result)
        return result

    monkeypatch.setattr(executor, "_compile_fused_pair_kernel", capture_build)
    monkeypatch.setattr(executor, "_build_fused_result", capture_result)
    original_get = registry.get
    missing = {"pending": lookup != "available"}

    def transient_get(name, *args, **kwargs):
        if name == _Consumer.signature.fqn and missing["pending"]:
            missing["pending"] = False
            if lookup == "raises_once":
                raise LookupError("transient synthetic lookup failure")
            return None
        return original_get(name, *args, **kwargs)

    monkeypatch.setattr(registry, "get", transient_get)
    result = executor.execute_heterogeneous_chain(chain, state=jnp.asarray(2.0), registry=registry)
    assert float(result.final_state) == pytest.approx(9.0)
    assert [node for node, _ in result.node_results] == [first.id, second.id]
    if lookup == "available":
        assert built == [(_Producer, _Consumer)]
        assert len(produced) == 2
        assert all(
            actual is recorded for (_, actual), recorded in zip(result.node_results, produced)
        )
    else:
        assert not missing["pending"]
        assert built == []
        assert produced == []
