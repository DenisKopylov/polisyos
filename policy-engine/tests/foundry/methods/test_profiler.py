from __future__ import annotations

import jax
import jax.numpy as jnp

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
from polisyos.foundry.methods.profiler import MethodProfiler


def _signature(name: str, *, backend: ComputeBackend) -> MethodSignature:
    unit = Unit(dimension="none", symbol="1")
    return MethodSignature(
        name=name,
        namespace="tests.profiler",
        version="1.0.0",
        input_slots=frozenset({SlotSpec(name="x", slot_type=SlotType.SCALAR, unit=unit)}),
        output_slots=frozenset({SlotSpec(name="y", slot_type=SlotType.SCALAR, unit=unit)}),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=backend,
        supports_jit=backend == ComputeBackend.JAX,
        supports_vmap=False,
        supports_grad=False,
    )


class _JittedMethod:
    signature = _signature("jitted", backend=ComputeBackend.JAX)
    metadata = MethodMetadata(description="jitted test method")
    pure_step = staticmethod(jax.jit(lambda state, params: {"y": state["x"] + 1}))


class _PlainMethod:
    signature = _signature("plain", backend=ComputeBackend.NUMPY)
    metadata = MethodMetadata(description="plain test method")

    @staticmethod
    def pure_step(state, params):
        del params
        return {"y": state["x"] + 1}


def test_profiler_reports_supported_jit_signal_for_jitted_methods() -> None:
    profiler = MethodProfiler(enable_tracemalloc=False)
    if hasattr(_JittedMethod.pure_step, "clear_cache"):
        _JittedMethod.pure_step.clear_cache()

    _, cold = profiler.profile(_JittedMethod, {"x": jnp.ones(())}, {})
    _, warm = profiler.profile(_JittedMethod, {"x": jnp.ones(())}, {})

    assert cold.jit_signal_supported is True
    assert cold.n_jit_compilations == 1
    assert warm.jit_signal_supported is True
    assert warm.n_jit_compilations == 0


def test_profiler_marks_unsupported_jit_signal_honestly() -> None:
    profiler = MethodProfiler(enable_tracemalloc=False)

    _, profile = profiler.profile(_PlainMethod, {"x": jnp.ones(())}, {})

    assert profile.jit_signal_supported is False
    assert profile.n_jit_compilations == 0
    assert "unsupported" in profile.to_markdown_table()
